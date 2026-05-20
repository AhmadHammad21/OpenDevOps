"""Proactive anomaly poller — runs as a background asyncio task.

Every POLL_INTERVAL_SECONDS it:
  1. Fetches CloudWatch alarms in ALARM state.
  2. Checks Lambda error rates against POLL_ERROR_THRESHOLD.
  3. For any *new* anomaly (not investigated within POLL_REINVESTIGATE_HOURS),
     auto-runs a full agent investigation and posts the result to Slack.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from agent.incident_keys import alarm_incident_key, lambda_metric_incident_key
from config import settings


def _claim_window_minutes() -> int:
    return max(1, settings.poll_reinvestigate_hours * 60)


async def _run_investigation(
    prompt: str, session_id: str
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Run a full agent investigation using the same streaming path as the chat endpoint."""
    import json

    from agent.core import get_agent
    from agent.turns import save_turn

    def _f(obj: Any, key: str, default: Any = None) -> Any:
        return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)

    config = {
        "configurable": {"thread_id": session_id},
        "recursion_limit": settings.max_tool_calls * 3 + 15,
    }

    tc_accum: dict[int, dict[str, Any]] = {}
    pending_calls: dict[str, dict[str, Any]] = {}
    tool_calls_log: list[dict[str, Any]] = []
    investigation_result: dict[str, Any] | None = None
    response_text = ""
    usage_meta: Any = None

    try:
        async with asyncio.timeout(settings.investigation_timeout):
            async for chunk, _meta in get_agent().astream(
                {"messages": [{"role": "user", "content": prompt}]},
                config=config,
                stream_mode="messages",
            ):
                um = getattr(chunk, "usage_metadata", None)
                if um:
                    usage_meta = um

                for tcc in getattr(chunk, "tool_call_chunks", []) or []:
                    idx = _f(tcc, "index", 0)
                    if idx not in tc_accum:
                        tc_accum[idx] = {"id": "", "name": "", "args_str": ""}
                    if tc_id := _f(tcc, "id"):
                        tc_accum[idx]["id"] = tc_id
                    if name := (_f(tcc, "name") or ""):
                        tc_accum[idx]["name"] += name
                    if args := (_f(tcc, "args") or ""):
                        tc_accum[idx]["args_str"] += args

                for tc in getattr(chunk, "tool_calls", []) or []:
                    tc_id = _f(tc, "id") or ""
                    name = _f(tc, "name") or ""
                    args = _f(tc, "args") or {}
                    if tc_id and name:
                        pending_calls[tc_id] = {
                            "tool": name,
                            "args": args if isinstance(args, dict) else {},
                        }

                content = getattr(chunk, "content", "")
                tc_id = getattr(chunk, "tool_call_id", None)

                if content and isinstance(content, str) and not tc_id:
                    response_text += content

                if tc_id:
                    for entry in tc_accum.values():
                        if eid := entry["id"]:
                            try:
                                eargs: Any = (
                                    json.loads(entry["args_str"]) if entry["args_str"] else {}
                                )
                            except json.JSONDecodeError:
                                eargs = {}
                            pending_calls[eid] = {"tool": entry["name"], "args": eargs}
                    tc_accum.clear()

                    call_info = pending_calls.pop(
                        tc_id,
                        {"tool": getattr(chunk, "name", None) or "unknown", "args": {}},
                    )
                    try:
                        result = json.loads(content)
                    except (json.JSONDecodeError, TypeError):
                        result = {"raw": str(content)[:500]}

                    tool_calls_log.append({
                        "tool": call_info["tool"],
                        "args": call_info["args"],
                        "result": result,
                    })
                    if call_info["tool"] == "submit_investigation":
                        investigation_result = call_info["args"]

    except Exception as e:
        logger.error("Poller investigation failed: {}", e)
        investigation_result = {
            "_status": "failed",
            "root_cause_summary": f"Investigation failed: {e}",
            "confidence": "LOW",
            "mitigation_steps": [
                "Re-investigate manually via the chat — use a higher MAX_TOOL_CALLS if needed.",
            ],
        }

    if (investigation_result and investigation_result.get("root_cause_summary")
            and "_status" not in investigation_result):
        steps = investigation_result.get("mitigation_steps", [])
        steps_text = "\n".join(f"- {s}" for s in steps) if steps else "_No steps provided._"
        confidence = investigation_result.get("confidence", "MEDIUM")
        assistant_text = (
            f"**Root Cause ({confidence} confidence):** "
            f"{investigation_result['root_cause_summary']}\n\n"
            f"**Mitigation Steps:**\n{steps_text}"
        )
    elif response_text.strip():
        assistant_text = response_text.strip()
    else:
        assistant_text = "Investigation completed. See tool calls for details."

    await save_turn(
        session_id=session_id,
        user_message=prompt,
        assistant_text=assistant_text,
        tool_calls_log=tool_calls_log,
        usage={
            "model": settings.llm_model,
            "input_tokens": _f(usage_meta, "input_tokens", 0) or 0,
            "output_tokens": _f(usage_meta, "output_tokens", 0) or 0,
            "latency_ms": 0,
        },
        source="event",
    )

    return investigation_result, tool_calls_log


async def _persist_and_notify(
    result: dict[str, Any], tool_calls_log: list[dict[str, Any]], session_id: str, dedup_key: str
) -> None:
    from agent.monitor_store import add_alert, add_notification, update_service
    from agent.turns import notify_slack

    status = result.pop("_status", "completed")
    services_affected = result.get("services_affected", [])
    service = services_affected[0] if services_affected else "unknown"
    root_cause = result.get("root_cause_summary", "")
    mitigation = result.get("mitigation_steps", [])
    confidence = result.get("confidence", "MEDIUM")
    resolution = "\n".join(mitigation) if isinstance(mitigation, list) else str(mitigation)

    slack_sent = False
    if settings.slack_webhook_url:
        if status == "failed":
            from integrations.slack_webhook import post_failed_investigation
            slack_sent = await post_failed_investigation(
                settings.slack_webhook_url, service, root_cause, session_id
            )
        else:
            slack_sent = await notify_slack(session_id, tool_calls_log)

    telegram_sent = False
    if settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            from integrations.telegram import post_failed_investigation as tg_fail
            from integrations.telegram import post_investigation as tg_ok

            if status == "failed":
                telegram_sent = await tg_fail(
                    settings.telegram_bot_token, settings.telegram_chat_id,
                    service, root_cause, session_id,
                )
            else:
                telegram_sent = await tg_ok(
                    settings.telegram_bot_token, settings.telegram_chat_id,
                    result, session_id,
                )
        except Exception as e:
            logger.error("Telegram delivery failed from poller: {}", e)

    update_service(service, status, root_cause)
    alert_id = await add_alert(
        service=service,
        error=root_cause,
        resolution=resolution,
        confidence=confidence,
        sns_sent=False,
        dedup_key=dedup_key,
        status=status,
        session_id=session_id,
        trigger_source="poller",
    )
    if alert_id:
        if settings.slack_webhook_url:
            await add_notification(alert_id, "slack", "delivered" if slack_sent else "failed")
        if settings.telegram_bot_token and settings.telegram_chat_id:
            await add_notification(alert_id, "telegram", "delivered" if telegram_sent else "failed")


async def _check_alarms() -> None:
    """Check CloudWatch alarms — each new ALARM state triggers an investigation."""
    import uuid

    from agent.monitor_store import (
        claim_incident,
        complete_incident,
        is_recent_alert,
        release_incident,
    )
    from tools.cloudwatch import get_alarms

    data = await asyncio.get_event_loop().run_in_executor(None, get_alarms, "ALARM")
    alarms = data.get("alarms", [])
    logger.debug("Poller: {} alarm(s) in ALARM state", len(alarms))
    for alarm in alarms:
        name = alarm.get("name", "unknown")
        reason = alarm.get("reason", "")
        metric = alarm.get("metric", "")
        key = alarm_incident_key(name)

        if await is_recent_alert(key):
            logger.debug("Poller: skipping alarm {} — already investigated recently", name)
            continue
        if not await claim_incident(key, "poller", _claim_window_minutes()):
            continue

        logger.info("Poller: new ALARM state detected — {}", name)

        prompt = (
            f'CloudWatch alarm "{name}" is in ALARM state.\n'
            f"Metric: {metric}\n"
            f"Reason: {reason}\n"
            "Please investigate the root cause and provide mitigation steps."
        )
        session_id = str(uuid.uuid4())
        logger.debug(
            "Poller: starting investigation for alarm {} (session {})",
            name, session_id[:8],
        )
        try:
            result, tool_calls_log = await _run_investigation(prompt, session_id)
            if result:
                logger.info(
                    "Poller: investigation complete for alarm {} — {}",
                    name, result.get("confidence", "?"),
                )
                status = result.get("_status", "completed")
                await _persist_and_notify(result, tool_calls_log, session_id, key)
                await complete_incident(key, status, session_id)
            else:
                await release_incident(key)
        except Exception:
            await release_incident(key)
            raise


async def _check_lambda_errors() -> None:
    """Check Lambda functions for error rates above the configured threshold."""
    import uuid

    from agent.monitor_store import (
        claim_incident,
        complete_incident,
        is_incident_claimed,
        release_incident,
    )
    from tools.lambda_ import get_lambda_error_rate, list_lambda_functions

    funcs = await asyncio.get_event_loop().run_in_executor(None, list_lambda_functions)
    fn_list = funcs.get("functions", [])[:20]
    logger.debug("Poller: checking error rates for {} Lambda function(s)", len(fn_list))
    for fn in fn_list:  # cap at 20 to avoid runaway API calls
        name = fn.get("name", "")
        if not name:
            continue

        window_hours = max(1 / 60, settings.poll_interval_seconds / 3600)
        metrics = await asyncio.get_event_loop().run_in_executor(
            None,
            get_lambda_error_rate,
            name,
            window_hours,
        )
        error_rate = metrics.get("error_rate_pct", 0) or 0
        if error_rate < settings.poll_error_threshold:
            continue

        # The aggregate alarm covers all Lambda errors — if it fired recently, skip.
        from agent.event_infra import ALARM_NAME
        aggregate_key = alarm_incident_key(ALARM_NAME)
        aggregate_window = max(3, (settings.investigation_timeout // 60) + 2)
        if await is_incident_claimed(aggregate_key, aggregate_window):
            logger.debug("Poller: skipping Lambda {} — aggregate alarm already handled", name)
            continue

        key = lambda_metric_incident_key(name)
        if not await claim_incident(key, "poller", _claim_window_minutes()):
            continue

        logger.info("Poller: Lambda {} error rate {:.1f}% exceeds threshold", name, error_rate)

        prompt = (
            f'Lambda function "{name}" has an error rate of {error_rate:.1f}% over the last hour, '
            f"which exceeds the {settings.poll_error_threshold}% threshold.\n"
            "Please investigate the root cause and suggest a fix."
        )
        session_id = str(uuid.uuid4())
        logger.debug(
            "Poller: starting investigation for Lambda {} (session {})",
            name, session_id[:8],
        )
        try:
            result, tool_calls_log = await _run_investigation(prompt, session_id)
            if result:
                logger.info(
                    "Poller: investigation complete for Lambda {} — {}",
                    name, result.get("confidence", "?"),
                )
                status = result.get("_status", "completed")
                await _persist_and_notify(result, tool_calls_log, session_id, key)
                await complete_incident(key, status, session_id)
            else:
                await release_incident(key)
        except Exception:
            await release_incident(key)
            raise


async def polling_loop() -> None:
    """Main loop — runs forever until cancelled."""
    interval = settings.poll_interval_seconds
    logger.info(
        "Poller started — interval={}s  error_threshold={}%  slack={}",
        settings.poll_interval_seconds,
        settings.poll_error_threshold,
        "enabled" if settings.slack_webhook_url else "disabled",
    )
    while True:
        await asyncio.sleep(interval)
        logger.debug("Poller tick — checking alarms and Lambda error rates")
        try:
            from agent.init_store import is_event_infra_enabled
            if not is_event_infra_enabled():
                # EventBridge → SQS already covers alarm state changes when infra is active
                await _check_alarms()
            await _check_lambda_errors()
            logger.debug("Poller tick complete — next check in {}s", interval)
        except Exception as e:
            logger.error("Poller tick failed: {}", e)
