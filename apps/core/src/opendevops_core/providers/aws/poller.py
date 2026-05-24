"""Proactive anomaly poller — runs as a background asyncio task.

Every POLL_INTERVAL_SECONDS it:
  1. Fetches CloudWatch alarms in ALARM state.
  2. Checks Lambda error rates against POLL_ERROR_THRESHOLD.
  3. For any *new* anomaly (not investigated within POLL_REINVESTIGATE_HOURS),
     auto-runs a full agent investigation and posts the result to Slack.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from loguru import logger

from opendevops_core.agent.incident_keys import (
    alarm_incident_key,
    lambda_error_incident_key,
)
from opendevops_core.config import settings

# Dedicated pool so poller boto3 calls never compete with API request threads
_POLLER_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="poller")


def _claim_window_minutes() -> int:
    return max(1, settings.poll_reinvestigate_hours * 60)


async def _run_investigation(
    prompt: str, session_id: str
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    from opendevops_core.agent.investigation_runner import run_investigation

    return await run_investigation(prompt, session_id)


async def _persist_and_notify(
    result: dict[str, Any], tool_calls_log: list[dict[str, Any]], session_id: str, dedup_key: str
) -> None:
    from opendevops_core.agent.monitor_store import add_alert, add_notification, update_service
    from opendevops_core.agent.turns import notify_slack

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
            from opendevops_core.integrations.slack_webhook import post_failed_investigation

            slack_sent = await post_failed_investigation(
                settings.slack_webhook_url, service, root_cause, session_id
            )
        else:
            slack_sent = await notify_slack(session_id, tool_calls_log)

    telegram_sent = False
    if settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            from opendevops_core.integrations.telegram import post_failed_investigation as tg_fail
            from opendevops_core.integrations.telegram import post_investigation as tg_ok

            if status == "failed":
                telegram_sent = await tg_fail(
                    settings.telegram_bot_token,
                    settings.telegram_chat_id,
                    service,
                    root_cause,
                    session_id,
                )
            else:
                telegram_sent = await tg_ok(
                    settings.telegram_bot_token,
                    settings.telegram_chat_id,
                    result,
                    session_id,
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
        evidence=result.get("evidence", []),
    )
    if alert_id:
        if settings.slack_webhook_url:
            await add_notification(alert_id, "slack", "delivered" if slack_sent else "failed")
        if settings.telegram_bot_token and settings.telegram_chat_id:
            await add_notification(alert_id, "telegram", "delivered" if telegram_sent else "failed")


async def _check_alarms() -> None:
    """Check CloudWatch alarms — each new ALARM state triggers an investigation."""
    import uuid

    from opendevops_core.agent.monitor_store import (
        claim_incident,
        complete_incident,
        is_recent_alert,
        release_incident,
    )
    from opendevops_core.providers.aws.tools.cloudwatch import get_alarms

    data = await asyncio.get_event_loop().run_in_executor(_POLLER_POOL, get_alarms, "ALARM")
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
        if alarm.get("state_reason"):
            logger.debug("Poller: alarm {} state reason: {}", name, alarm["state_reason"])

        namespace = alarm.get("namespace", "")
        dim_hint = (
            "IMPORTANT: If this alarm has NO dimensions it monitors the AGGREGATE metric "
            "across all resources. You MUST first identify which specific resource is causing "
            "the errors. For Lambda errors: call list_lambda_functions, then use "
            "get_lambda_error_rate on likely functions to find which one(s) have errors. "
            "Then pull that function's CloudWatch logs to find the actual error message."
            if namespace == "AWS/Lambda"
            else f"Namespace: {namespace}"
        )
        prompt = (
            f'CloudWatch alarm "{name}" is in ALARM state.\n'
            f"Metric: {metric}\n"
            f"{dim_hint}\n"
            f"Reason: {reason}\n\n"
            "Investigate step by step:\n"
            "1. Identify the SPECIFIC resource causing the issue\n"
            "2. Pull its recent CloudWatch logs\n"
            "3. Find the actual error message or stack trace\n"
            "4. Provide actionable fix steps based on the real error"
        )
        session_id = str(uuid.uuid4())
        logger.debug(
            "Poller: starting investigation for alarm {} (session {})",
            name,
            session_id[:8],
        )
        try:
            result, tool_calls_log = await _run_investigation(prompt, session_id)
            if result:
                logger.info(
                    "Poller: investigation complete for alarm {} — {}",
                    name,
                    result.get("confidence", "?"),
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

    from opendevops_core.agent.monitor_store import (
        claim_incident,
        complete_incident,
        is_incident_claimed,
        release_incident,
    )
    from opendevops_core.providers.aws.tools.lambda_ import (
        get_lambda_error_rate,
        list_lambda_functions,
    )

    funcs = await asyncio.get_event_loop().run_in_executor(_POLLER_POOL, list_lambda_functions)
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
        from opendevops_core.providers.aws.event_infra import ALARM_NAME

        aggregate_key = alarm_incident_key(ALARM_NAME)
        aggregate_window = max(3, (settings.investigation_timeout // 60) + 2)
        if await is_incident_claimed(aggregate_key, aggregate_window):
            logger.debug("Poller: skipping Lambda {} — aggregate alarm already handled", name)
            continue

        error_message = metrics.get("error_message")
        error_signature = {"errorMessage": error_message} if error_message else None
        key = lambda_error_incident_key(name, error_signature)
        if not await claim_incident(key, "poller", _claim_window_minutes()):
            continue

        logger.info("Poller: Lambda {} error rate {:.1f}% exceeds threshold", name, error_rate)
        if error_message:
            logger.debug("Poller: Lambda {} error message: {}", name, error_message)

        prompt = (
            f'Lambda function "{name}" has an error rate of {error_rate:.1f}% over the last hour, '
            f"which exceeds the {settings.poll_error_threshold}% threshold.\n\n"
            "Investigate step by step:\n"
            "1. Pull the recent CloudWatch logs for this function\n"
            "2. Find the actual error message or stack trace\n"
            "3. Identify the root cause (code bug, missing dependency, config issue, etc.)\n"
            "4. Provide specific, actionable fix steps based on the real error"
        )
        session_id = str(uuid.uuid4())
        logger.debug(
            "Poller: starting investigation for Lambda {} (session {})",
            name,
            session_id[:8],
        )
        try:
            result, tool_calls_log = await _run_investigation(prompt, session_id)
            if result:
                logger.info(
                    "Poller: investigation complete for Lambda {} — {}",
                    name,
                    result.get("confidence", "?"),
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
            from opendevops_core.agent.init_store import is_event_infra_enabled

            if not is_event_infra_enabled():
                # EventBridge → SQS already covers alarm state changes when infra is active
                await _check_alarms()
            await _check_lambda_errors()
            logger.debug("Poller tick complete — next check in {}s", interval)
        except Exception as e:
            logger.error("Poller tick failed: {}", e)
