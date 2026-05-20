"""Event consumer — long-polls SQS, runs full agent investigation, delivers result."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Literal

import boto3
from loguru import logger

from agent.incident_keys import event_incident_key
from agent.init_store import (
    get_runtime_aws_region,
    get_runtime_sns_topic_arn,
    get_runtime_sqs_queue_url,
)
from agent.monitor_store import (
    add_alert,
    add_notification,
    claim_incident,
    complete_incident,
    release_incident,
    update_service,
)
from config import settings

ProcessResult = Literal["processed", "ignored", "duplicate"]


def _build_investigation_prompt(event: dict) -> str:
    """Turn a raw EventBridge event into a focused investigation prompt."""
    source = event.get("source", "unknown")
    detail_type = event.get("detail-type", "")
    detail = event.get("detail", {})
    time = event.get("time", "")

    if source == "aws.cloudwatch" and "alarmName" in detail:
        alarm_name = detail["alarmName"]
        reason = detail.get("state", {}).get("reason", "")
        metric = (
            detail.get("configuration", {})
            .get("metrics", [{}])[0]
            .get("metricStat", {})
            .get("metric", {})
        )
        namespace = metric.get("namespace", "")
        metric_name = metric.get("name", "")
        dimensions = metric.get("dimensions", {})

        if not dimensions:
            dim_hint = (
                "IMPORTANT: This alarm has NO dimensions — it monitors the AGGREGATE "
                "metric across all resources. "
                "You MUST first identify which specific resource is causing the errors. "
                "For Lambda errors: call list_lambda_functions, then use "
                "get_lambda_error_rate on likely functions "
                "to find which function(s) have errors. "
                "Then pull that function's CloudWatch logs to find the actual error message."
            )
        else:
            dim_hint = (
                f"Dimensions: {json.dumps(dimensions)} — use these to identify the "
                "specific resource."
            )

        return (
            f'CloudWatch alarm "{alarm_name}" triggered at {time}.\n'
            f"Namespace: {namespace}\n"
            f"Metric: {metric_name}\n"
            f"{dim_hint}\n"
            f"Reason: {reason}\n\n"
            "Investigate step by step:\n"
            "1. Identify the SPECIFIC resource causing the issue\n"
            "2. Pull its recent CloudWatch logs\n"
            "3. Find the actual error message or stack trace\n"
            "4. Provide actionable fix steps based on the real error"
        )

    if source == "aws.lambda":
        fn_name = (
            detail.get("functionName", "")
            or detail.get("requestContext", {}).get("functionArn", "").split(":")[-1]
        )
        error_type = detail.get("condition", detail_type)
        return (
            f'Lambda function "{fn_name}" reported: {error_type} at {time}.\n'
            f"Detail: {json.dumps(detail, default=str)[:2000]}\n\n"
            "Investigate: pull the recent CloudWatch logs for this function, "
            "identify the exact error/exception, and provide specific fix steps."
        )

    if source == "aws.ecs":
        cluster = detail.get("clusterArn", "").split("/")[-1]
        reason = detail.get("stoppedReason", "")
        return (
            f'ECS task stopped in cluster "{cluster}" at {time}.\n'
            f"Stopped reason: {reason}\n"
            f"Detail: {json.dumps(detail, default=str)[:2000]}\n\n"
            "Investigate: identify the container that failed, pull its logs, "
            "find the error, and provide fix steps."
        )

    return (
        f"AWS event detected from {source} ({detail_type}) at {time}.\n"
        f"Detail: {json.dumps(detail, default=str)[:3000]}\n\n"
        "Investigate the root cause: identify the affected resource, "
        "pull relevant logs and metrics, find the actual error, and provide actionable fix steps."
    )


async def _run_investigation(prompt: str, session_id: str) -> dict[str, Any] | None:
    from agent.investigation_runner import run_investigation
    result, _tool_calls_log = await run_investigation(prompt, session_id)
    return result


def _extract_aws_error(event: dict) -> str:
    """Pull the original AWS error message out of the event payload."""
    source = event.get("source", "")
    detail = event.get("detail", {})
    if source == "aws.lambda":
        return detail.get("responsePayload", {}).get("errorMessage", "")
    if source == "aws.cloudwatch":
        return detail.get("state", {}).get("reason", "")
    if source == "aws.ecs":
        return detail.get("stoppedReason", "")
    if source == "aws.rds":
        return detail.get("Message", "")
    return ""


async def _deliver(result: dict[str, Any], event: dict, dedup_key: str, session_id: str) -> None:
    """Send investigation result to SNS + Slack and persist to the monitor store."""
    status = result.pop("_status", "completed")
    is_test = bool(event.get("_opendevops_test", False))
    services_affected = result.get("services_affected", [])
    fallback = services_affected[0] if services_affected else event.get("source", "unknown")
    service = result.get("service_name", result.get("service", fallback))
    root_cause = result.get("root_cause_summary", "")
    mitigation = result.get("mitigation_steps", [])
    confidence = result.get("confidence", "MEDIUM")
    resolution = "\n".join(mitigation) if isinstance(mitigation, list) else str(mitigation)
    aws_error = _extract_aws_error(event)

    sns_arn = get_runtime_sns_topic_arn()

    sns_sent = False
    sns_attempted = False
    if sns_arn:
        sns_attempted = True
        try:
            from tools.sns import publish_sns_alert

            services_affected = result.get("services_affected", [])
            evidence = result.get("evidence", [])
            message = (
                f"Service: {service}\n"
                f"Root Cause: {root_cause}\n"
                f"Evidence: {chr(10).join(evidence[:5]) if evidence else 'N/A'}\n"
                f"Mitigation Steps:\n{resolution}\n"
                "Services Affected: "
                f"{', '.join(services_affected) if services_affected else service}\n"
                f"Confidence: {confidence}\n"
                f"Event Time: {event.get('time', '')}"
            )
            subject_prefix = "[FAILED]" if status == "failed" else f"[{confidence}]"
            await asyncio.get_event_loop().run_in_executor(
                None,
                publish_sns_alert,
                sns_arn,
                f"{subject_prefix} {service} — {root_cause[:80]}",
                message,
            )
            sns_sent = True
        except Exception as e:
            logger.error("SNS delivery failed: {}", e)

    slack_sent = False
    if settings.slack_webhook_url:
        try:
            from integrations.slack_webhook import post_failed_investigation, post_investigation

            if status == "failed":
                slack_sent = await post_failed_investigation(
                    settings.slack_webhook_url, service, root_cause,
                    session_id, aws_error=aws_error, is_test=is_test,
                )
            else:
                slack_sent = await post_investigation(
                    settings.slack_webhook_url, result, session_id, is_test=is_test
                )
        except Exception as e:
            logger.error("Slack delivery failed from event consumer: {}", e)

    telegram_sent = False
    if settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            from integrations.telegram import post_failed_investigation as tg_fail
            from integrations.telegram import post_investigation as tg_ok

            if status == "failed":
                telegram_sent = await tg_fail(
                    settings.telegram_bot_token, settings.telegram_chat_id,
                    service, root_cause, session_id, is_test=is_test,
                )
            else:
                telegram_sent = await tg_ok(
                    settings.telegram_bot_token, settings.telegram_chat_id,
                    result, session_id, is_test=is_test,
                )
        except Exception as e:
            logger.error("Telegram delivery failed from event consumer: {}", e)

    update_service(service, status, root_cause)
    alert_id = await add_alert(
        service=service,
        error=root_cause,
        resolution=resolution,
        confidence=confidence,
        sns_sent=sns_sent,
        dedup_key=dedup_key,
        status=status,
        session_id=session_id,
        trigger_source="event_consumer",
        evidence=result.get("evidence", []),
    )
    if alert_id:
        if sns_attempted:
            await add_notification(alert_id, "sns", "delivered" if sns_sent else "failed")
        if settings.slack_webhook_url:
            await add_notification(alert_id, "slack", "delivered" if slack_sent else "failed")
        if settings.telegram_bot_token and settings.telegram_chat_id:
            await add_notification(alert_id, "telegram", "delivered" if telegram_sent else "failed")
    logger.info("Alert delivered: service={} confidence={} sns={}", service, confidence, sns_sent)


def _is_real_failure(source: str, detail: dict) -> bool:
    """Return True only if this event represents a real failure worth investigating."""
    if source == "aws.ecs":
        containers = detail.get("containers", [])
        if containers and all(c.get("exitCode") == 0 for c in containers):
            return False
        stop_code = detail.get("stopCode", "")
        if stop_code in ("UserInitiated", "ServiceSchedulerInitiated"):
            return False
        return True

    if source == "aws.rds":
        categories = detail.get("EventCategories", [])
        return any(c in categories for c in ("failure", "failover"))

    return True


def _claim_window_minutes() -> int:
    return max(3, (settings.investigation_timeout // 60) + 2)


async def _process_event(event: dict) -> ProcessResult:
    """Filter → dedup check → enrich prompt → investigate → deliver."""
    source = event.get("source", "unknown")
    detail_type = event.get("detail-type", "")
    detail = event.get("detail", {})

    if not _is_real_failure(source, detail):
        logger.debug("Skipping non-failure event: {} / {}", source, detail_type)
        return "ignored"

    incident_key = event_incident_key(event)
    if not await claim_incident(incident_key, "event_consumer", _claim_window_minutes()):
        logger.info(
            "Dedup: skipping {} / {} (incident_key={}) — already claimed recently",
            source, detail_type, incident_key,
        )
        return "duplicate"

    logger.info("Processing event: {} / {} (incident_key={})", source, detail_type, incident_key)
    aws_error = _extract_aws_error(event)
    if aws_error:
        logger.debug("Event consumer: error message for investigation: {}", aws_error)

    prompt = _build_investigation_prompt(event)

    # Enrich prompt with deterministic boto3 context (no LLM cost)
    try:
        from agent.context_collectors import collect_context

        context = collect_context(event)
        if context and not context.get("error"):
            context_str = json.dumps(context, default=str)
            prompt = (
                prompt
                + "\n\nPre-collected context (use as starting facts, verify with tools):\n"
                + context_str[:3000]
            )
    except Exception as e:
        logger.debug("Context collection skipped: {}", e)

    session_id = str(uuid.uuid4())
    try:
        logger.debug(
            "Event consumer: starting investigation for {} / {} (session {})",
            source, detail_type, session_id[:8],
        )
        result = await _run_investigation(prompt, session_id)
        if not result:
            logger.warning("Investigation produced no result for {} / {}", source, detail_type)
            await release_incident(incident_key)
            raise RuntimeError("Investigation produced no structured result")
        status = result.get("_status", "completed")
        await _deliver(result, event, incident_key, session_id)
        await complete_incident(incident_key, status, session_id)
        return "processed"
    except Exception:
        await release_incident(incident_key)
        raise


async def event_consumer_loop() -> None:
    """Main loop — long-polls SQS, processes events."""
    queue_url = get_runtime_sqs_queue_url()
    if not queue_url:
        logger.warning("No SQS queue URL configured — event consumer not starting")
        return

    s = (
        boto3.Session(profile_name=settings.aws_profile)
        if settings.aws_profile
        else boto3.Session()
    )
    sqs = s.client("sqs", region_name=get_runtime_aws_region())

    logger.info("Event consumer started — polling {}", queue_url)

    while True:
        try:
            resp = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: sqs.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=5,
                    WaitTimeSeconds=20,
                ),
            )

            for msg in resp.get("Messages", []):
                should_delete = False
                try:
                    body = json.loads(msg["Body"])
                    await _process_event(body)
                    should_delete = True
                except json.JSONDecodeError as e:
                    logger.error("Failed to decode SQS event body: {}", e)
                except Exception as e:
                    logger.error("Failed to process event: {}", e)
                if should_delete:
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda m=msg: sqs.delete_message(
                            QueueUrl=queue_url, ReceiptHandle=m["ReceiptHandle"]
                        ),
                    )

        except asyncio.CancelledError:
            logger.info("Event consumer shutting down")
            break
        except Exception as e:
            logger.error("Event consumer error: {}", e)
            await asyncio.sleep(5)
