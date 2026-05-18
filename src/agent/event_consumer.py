"""Event consumer — long-polls SQS, runs full agent investigation, delivers result."""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from typing import Any

import boto3
from loguru import logger

from agent.init_store import (
    get_runtime_aws_region,
    get_runtime_sns_topic_arn,
    get_runtime_sqs_queue_url,
)
from agent.monitor_store import add_alert, is_recent_alert, update_service
from config import settings

# In-memory set of dedup keys currently being investigated.
# Prevents a second identical event from starting a parallel agent run
# before the first one finishes and writes its key to the DB.
_in_progress: set[str] = set()


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
    """Run a full agent investigation, persist the session, and return the result."""
    from agent.core import get_agent
    from agent.turns import save_turn

    config = {
        "configurable": {"thread_id": session_id},
        "recursion_limit": settings.max_tool_calls * 3 + 15,
    }

    investigation_result: dict[str, Any] | None = None
    messages: list = []

    try:
        result = await get_agent().ainvoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config=config,
        )
        messages = result.get("messages", [])
        for msg in reversed(messages):
            for tc in getattr(msg, "tool_calls", []) or []:
                name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
                if name == "submit_investigation":
                    investigation_result = args
                    break
            if investigation_result:
                break
        if not investigation_result and messages:
            last = messages[-1]
            content = last.content if hasattr(last, "content") else str(last)
            if content:
                investigation_result = {
                    "root_cause_summary": content,
                    "confidence": "MEDIUM",
                    "mitigation_steps": [],
                }
    except Exception as e:
        logger.error("Agent investigation failed: {}", e)
        investigation_result = {
            "_status": "failed",
            "root_cause_summary": f"Investigation failed: {e}",
            "confidence": "LOW",
            "mitigation_steps": [
                "The agent hit its tool call limit or encountered an error.",
                "Re-investigate manually via the chat — use a higher MAX_TOOL_CALLS if needed.",
            ],
        }

    # Persist the session regardless of success/failure
    input_tokens, output_tokens = 0, 0
    for msg in messages:
        um = getattr(msg, "usage_metadata", None) or {}
        input_tokens += um.get("input_tokens", 0)
        output_tokens += um.get("output_tokens", 0)

    # Build a readable assistant summary from the investigation result
    if investigation_result and investigation_result.get("root_cause_summary"):
        steps = investigation_result.get("mitigation_steps", [])
        steps_text = (
            "\n".join(f"- {s}" for s in steps) if steps else "_No steps provided._"
        )
        confidence = investigation_result.get("confidence", "MEDIUM")
        assistant_text = (
            f"**Root Cause ({confidence} confidence):** "
            f"{investigation_result['root_cause_summary']}\n\n"
            f"**Mitigation Steps:**\n{steps_text}"
        )
    else:
        assistant_text = "Investigation completed. See tool calls for details."

    await save_turn(
        session_id=session_id,
        user_message=prompt,
        assistant_text=assistant_text,
        tool_calls_log=[],
        usage={
            "model": settings.llm_model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": 0,
        },
        source="event",
    )

    return investigation_result


_VOLATILE_KEYS = {
    "time", "timestamp", "eventTime", "requestId", "eventID",
    "approximateInvokeCount", "startTime", "endTime", "updatedAt",
    "stateTransitionedAt", "lastUpdatedTime",
}


def _strip_volatile(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_volatile(v) for k, v in obj.items() if k not in _VOLATILE_KEYS}
    if isinstance(obj, list):
        return [_strip_volatile(i) for i in obj]
    return obj


def _event_dedup_key(event: dict) -> str:
    """MD5 fingerprint of the event's stable fields — works for any AWS service."""
    source = event.get("source", "unknown")
    fingerprint = {
        "source": source,
        "detail-type": event.get("detail-type", ""),
        "detail": _strip_volatile(event.get("detail", {})),
    }
    digest = hashlib.md5(
        json.dumps(fingerprint, sort_keys=True, default=str).encode()
    ).hexdigest()[:12]
    return f"{source}:{digest}"


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
    if sns_arn:
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

    # Also notify Slack (keeps parity with the poller)
    if settings.slack_webhook_url:
        try:
            from integrations.slack_webhook import post_failed_investigation, post_investigation

            if status == "failed":
                await post_failed_investigation(
                    settings.slack_webhook_url, service, root_cause,
                    session_id, aws_error=aws_error, is_test=is_test,
                )
            else:
                await post_investigation(
                    settings.slack_webhook_url, result, session_id, is_test=is_test
                )
        except Exception as e:
            logger.error("Slack delivery failed from event consumer: {}", e)

    update_service(service, status, root_cause)
    await add_alert(
        service=service,
        error=root_cause,
        resolution=resolution,
        confidence=confidence,
        sns_sent=sns_sent,
        dedup_key=dedup_key,
        status=status,
        session_id=session_id,
    )
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


async def _process_event(event: dict) -> None:
    """Filter → dedup check → enrich prompt → investigate → deliver."""
    source = event.get("source", "unknown")
    detail_type = event.get("detail-type", "")
    detail = event.get("detail", {})

    if not _is_real_failure(source, detail):
        logger.debug("Skipping non-failure event: {} / {}", source, detail_type)
        return

    dedup_key = _event_dedup_key(event)
    if dedup_key in _in_progress or await is_recent_alert(dedup_key):
        logger.info(
            "Dedup: skipping {} / {} (key={}) — {}",
            source, detail_type, dedup_key,
            "investigation already in progress" if dedup_key in _in_progress
            else "same event investigated within last 3 min",
        )
        return

    _in_progress.add(dedup_key)
    logger.info("Processing event: {} / {}", source, detail_type)

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
        result = await _run_investigation(prompt, session_id)
        if not result:
            logger.warning("Investigation produced no result for {} / {}", source, detail_type)
            return
        await _deliver(result, event, dedup_key, session_id)
    finally:
        _in_progress.discard(dedup_key)


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
                try:
                    body = json.loads(msg["Body"])
                    await _process_event(body)
                except Exception as e:
                    logger.error("Failed to process event: {}", e)
                finally:
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
