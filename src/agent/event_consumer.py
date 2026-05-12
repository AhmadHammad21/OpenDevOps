"""Event consumer — long-polls SQS, runs full agent investigation, delivers result."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import boto3
from loguru import logger

from config import settings
from agent.init_store import load_init
from agent.monitor_store import add_alert


def _build_investigation_prompt(event: dict) -> str:
    """Turn a raw EventBridge event into a focused investigation prompt."""
    source = event.get("source", "unknown")
    detail_type = event.get("detail-type", "")
    detail = event.get("detail", {})
    time = event.get("time", "")

    if source == "aws.cloudwatch" and "alarmName" in detail:
        alarm_name = detail["alarmName"]
        reason = detail.get("state", {}).get("reason", "")
        metric = detail.get("configuration", {}).get("metrics", [{}])[0].get("metricStat", {}).get("metric", {})
        namespace = metric.get("namespace", "")
        metric_name = metric.get("name", "")
        dimensions = metric.get("dimensions", {})

        if not dimensions:
            dim_hint = (
                "IMPORTANT: This alarm has NO dimensions — it monitors the AGGREGATE metric across all resources. "
                "You MUST first identify which specific resource is causing the errors. "
                "For Lambda errors: use get_metric_data with a SEARCH expression like "
                "SEARCH('{AWS/Lambda,FunctionName} MetricName=\"Errors\"', 'Sum', 300) to find which function(s) have errors. "
                "Then pull that function's CloudWatch logs to find the actual error message."
            )
        else:
            dim_hint = f"Dimensions: {json.dumps(dimensions)} — use these to identify the specific resource."

        return (
            f'CloudWatch alarm "{alarm_name}" triggered at {time}.\n'
            f"Namespace: {namespace}\n"
            f"Metric: {metric_name}\n"
            f"{dim_hint}\n"
            f"Reason: {reason}\n\n"
            "Investigate step by step:\n"
            "1. Identify the SPECIFIC resource (function name, instance ID, etc.) causing the issue\n"
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


async def _run_investigation(prompt: str) -> dict[str, Any] | None:
    """Run a full agent investigation and return the submit_investigation result."""
    from agent.core import get_agent

    thread_id = str(uuid.uuid4())
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": settings.max_tool_calls * 3 + 15,
    }

    try:
        result = await get_agent().ainvoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config=config,
        )
        for msg in reversed(result.get("messages", [])):
            for tc in getattr(msg, "tool_calls", []) or []:
                name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
                if name == "submit_investigation":
                    return args
        messages = result.get("messages", [])
        if messages:
            last = messages[-1]
            content = last.content if hasattr(last, "content") else str(last)
            if content:
                return {"root_cause_summary": content, "confidence": "MEDIUM", "mitigation_steps": []}
    except Exception as e:
        logger.error("Agent investigation failed: {}", e)
    return None


async def _deliver(result: dict[str, Any], event: dict) -> None:
    """Send investigation result to SNS + Slack and persist to the monitor store."""
    services_affected = result.get("services_affected", [])
    service = result.get("service_name", result.get("service",
        services_affected[0] if services_affected else "unknown"
    ))
    root_cause = result.get("root_cause_summary", "")
    mitigation = result.get("mitigation_steps", [])
    confidence = result.get("confidence", "MEDIUM")
    resolution = "\n".join(mitigation) if isinstance(mitigation, list) else str(mitigation)

    init_data = load_init()
    sns_arn = settings.sns_topic_arn or init_data.get("sns_topic_arn")

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
                f"Services Affected: {', '.join(services_affected) if services_affected else service}\n"
                f"Confidence: {confidence}\n"
                f"Event Time: {event.get('time', '')}"
            )
            await asyncio.get_event_loop().run_in_executor(
                None, publish_sns_alert, sns_arn, f"[{confidence}] {service} — {root_cause[:80]}", message
            )
            sns_sent = True
        except Exception as e:
            logger.error("SNS delivery failed: {}", e)

    # Also notify Slack (keeps parity with the poller)
    if settings.slack_webhook_url:
        try:
            from integrations.slack_webhook import post_investigation
            session_id = str(uuid.uuid4())
            await post_investigation(settings.slack_webhook_url, result, session_id)
        except Exception as e:
            logger.error("Slack delivery failed from event consumer: {}", e)

    add_alert(service=service, error=root_cause, resolution=resolution, confidence=confidence, sns_sent=sns_sent)
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
    """Filter → enrich prompt → investigate → deliver."""
    source = event.get("source", "unknown")
    detail_type = event.get("detail-type", "")
    detail = event.get("detail", {})

    if not _is_real_failure(source, detail):
        logger.debug("Skipping non-failure event: {} / {}", source, detail_type)
        return

    logger.info("Processing event: {} / {}", source, detail_type)

    prompt = _build_investigation_prompt(event)

    # Enrich prompt with deterministic boto3 context (no LLM cost)
    try:
        from agent.context_collectors import collect_context
        context = collect_context(event)
        if context and not context.get("error"):
            context_str = json.dumps(context, default=str)
            prompt = prompt + f"\n\nPre-collected context (use as starting facts, verify with tools):\n{context_str[:3000]}"
    except Exception as e:
        logger.debug("Context collection skipped: {}", e)

    result = await _run_investigation(prompt)
    if result:
        await _deliver(result, event)
    else:
        logger.warning("Investigation produced no result for {} / {}", source, detail_type)


async def event_consumer_loop() -> None:
    """Main loop — long-polls SQS, processes events."""
    init_data = load_init()
    # Prefer env var over init.json so users can configure via .env without the wizard
    queue_url = settings.sqs_queue_url or init_data.get("sqs_queue_url")
    if not queue_url:
        logger.warning("No SQS queue URL configured — event consumer not starting")
        return

    s = boto3.Session(profile_name=settings.aws_profile) if settings.aws_profile else boto3.Session()
    sqs = s.client("sqs", region_name=settings.aws_region)

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
