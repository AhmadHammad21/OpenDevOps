"""Proactive anomaly poller — runs as a background asyncio task.

Every POLL_INTERVAL_SECONDS it:
  1. Fetches CloudWatch alarms in ALARM state.
  2. Checks Lambda error rates against POLL_ERROR_THRESHOLD.
  3. For any *new* anomaly (not investigated within POLL_REINVESTIGATE_HOURS),
     auto-runs a full agent investigation and posts the result to Slack.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger

from config import settings

# In-memory dedup: maps a trigger key → datetime last investigated.
# Resets on process restart (intentional — re-check on startup is fine).
_last_investigated: dict[str, datetime] = {}


def _should_investigate(key: str) -> bool:
    last = _last_investigated.get(key)
    if last is None:
        return True
    return datetime.now(UTC) - last > timedelta(hours=settings.poll_reinvestigate_hours)


def _mark_investigated(key: str) -> None:
    _last_investigated[key] = datetime.now(UTC)


async def _run_investigation(prompt: str, trigger_key: str) -> dict[str, Any] | None:
    """Invoke the agent synchronously in a thread and return the submit_investigation args."""
    import uuid

    from agent.core import get_agent

    thread_id = str(uuid.uuid4())
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": settings.max_tool_calls * 3 + 15,
    }

    try:
        agent = get_agent()
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config=config,
        )
        # Extract submit_investigation args from tool calls in the message history
        for msg in reversed(result.get("messages", [])):
            for tc in getattr(msg, "tool_calls", []) or []:
                name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
                if name == "submit_investigation":
                    return args
    except Exception as e:
        logger.error("Poller investigation failed for {}: {}", trigger_key, e)
    return None


async def _persist_and_notify(prompt: str, result: dict[str, Any], session_id: str) -> None:
    from agent.monitor_store import add_alert, update_service
    from agent.turns import notify_slack, save_turn

    tool_calls_log = [{"tool": "submit_investigation", "args": result, "result": {}}]
    usage = {"model": settings.llm_model, "latency_ms": 0}
    await save_turn(session_id, prompt, "", tool_calls_log, usage)
    await notify_slack(session_id, tool_calls_log)

    services_affected = result.get("services_affected", [])
    service = services_affected[0] if services_affected else "unknown"
    root_cause = result.get("root_cause_summary", "")
    mitigation = result.get("mitigation_steps", [])
    confidence = result.get("confidence", "MEDIUM")
    resolution = "\n".join(mitigation) if isinstance(mitigation, list) else str(mitigation)
    update_service(service, "error", root_cause)
    await add_alert(
        service=service,
        error=root_cause,
        resolution=resolution,
        confidence=confidence,
        sns_sent=False,
    )


async def _check_alarms() -> None:
    """Check CloudWatch alarms — each new ALARM state triggers an investigation."""
    import uuid

    from tools.cloudwatch import get_alarms

    data = await asyncio.get_event_loop().run_in_executor(None, get_alarms, "ALARM")
    for alarm in data.get("alarms", []):
        name = alarm.get("name", "unknown")
        reason = alarm.get("reason", "")
        metric = alarm.get("metric", "")
        key = f"alarm:{name}"

        if not _should_investigate(key):
            continue

        logger.info("Poller: new ALARM state detected — {}", name)
        _mark_investigated(key)

        prompt = (
            f'CloudWatch alarm "{name}" is in ALARM state.\n'
            f"Metric: {metric}\n"
            f"Reason: {reason}\n"
            "Please investigate the root cause and provide mitigation steps."
        )
        session_id = str(uuid.uuid4())
        result = await _run_investigation(prompt, key)
        if result:
            logger.info("Poller investigation complete for alarm: {}", name)
            await _persist_and_notify(prompt, result, session_id)


async def _check_lambda_errors() -> None:
    """Check Lambda functions for error rates above the configured threshold."""
    import uuid

    from tools.lambda_ import get_lambda_error_rate, list_lambda_functions

    funcs = await asyncio.get_event_loop().run_in_executor(None, list_lambda_functions)
    for fn in funcs.get("functions", [])[:20]:  # cap at 20 to avoid runaway API calls
        name = fn.get("name", "")
        if not name:
            continue

        metrics = await asyncio.get_event_loop().run_in_executor(
            None,
            get_lambda_error_rate,
            name,
            1,  # last 1 hour
        )
        error_rate = metrics.get("error_rate_pct", 0) or 0
        if error_rate < settings.poll_error_threshold:
            continue

        key = f"lambda_errors:{name}"
        if not _should_investigate(key):
            continue

        logger.info("Poller: Lambda {} error rate {:.1f}% exceeds threshold", name, error_rate)
        _mark_investigated(key)

        prompt = (
            f'Lambda function "{name}" has an error rate of {error_rate:.1f}% over the last hour, '
            f"which exceeds the {settings.poll_error_threshold}% threshold.\n"
            "Please investigate the root cause and suggest a fix."
        )
        session_id = str(uuid.uuid4())
        result = await _run_investigation(prompt, key)
        if result:
            logger.info("Poller investigation complete for Lambda: {}", name)
            await _persist_and_notify(prompt, result, session_id)


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
        logger.debug("Poller tick")
        try:
            await _check_alarms()
            await _check_lambda_errors()
        except Exception as e:
            logger.error("Poller tick failed: {}", e)
