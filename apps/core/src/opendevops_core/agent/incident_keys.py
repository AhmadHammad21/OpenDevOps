"""Canonical incident keys shared by poller and event consumer."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from opendevops_core.config import settings

_VOLATILE_KEYS = {
    "time",
    "timestamp",
    "eventTime",
    "requestId",
    "eventID",
    "approximateInvokeCount",
    "startTime",
    "endTime",
    "updatedAt",
    "stateTransitionedAt",
    "lastUpdatedTime",
}


def _part(value: Any, fallback: str = "unknown") -> str:
    text = str(value or fallback).strip().lower()
    text = re.sub(r"[^a-z0-9_.:/-]+", "-", text).strip("-")
    return text[:160] or fallback


def _digest(value: Any, length: int = 12) -> str:
    encoded = json.dumps(value, sort_keys=True, default=str).encode()
    return hashlib.sha1(encoded).hexdigest()[:length]


def _strip_volatile(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_volatile(v) for k, v in obj.items() if k not in _VOLATILE_KEYS}
    if isinstance(obj, list):
        return [_strip_volatile(i) for i in obj]
    return obj


def _region(value: str | None = None) -> str:
    return _part(value or settings.aws_region)


def alarm_incident_key(alarm_name: str, region: str | None = None) -> str:
    return f"cloudwatch_alarm:{_region(region)}:{_part(alarm_name)}"


def lambda_metric_incident_key(function_name: str, region: str | None = None) -> str:
    return f"lambda_errors:{_region(region)}:{_part(function_name)}"


def lambda_error_incident_key(
    function_name: str,
    error_signature: Any | None = None,
    region: str | None = None,
) -> str:
    if error_signature:
        return f"lambda_error:{_region(region)}:{_part(function_name)}:{_digest(error_signature)}"
    return lambda_metric_incident_key(function_name, region)


def event_incident_key(event: dict[str, Any]) -> str:
    """Build a stable incident key from the resource identity, not event delivery metadata."""
    source = event.get("source", "unknown")
    detail_type = event.get("detail-type", "")
    detail = event.get("detail", {}) if isinstance(event.get("detail", {}), dict) else {}
    region = event.get("region") or settings.aws_region

    if source == "aws.cloudwatch" and "alarmName" in detail:
        return alarm_incident_key(str(detail.get("alarmName", "unknown")), region)

    if source == "aws.lambda":
        request_context = detail.get("requestContext", {})
        function_name = (
            detail.get("functionName")
            or str(request_context.get("functionArn", "")).split(":")[-1]
            or str(detail.get("functionArn", "")).split(":")[-1]
            or "unknown"
        )
        payload = detail.get("responsePayload", {})
        payload = payload if isinstance(payload, dict) else {}
        error_signature = {
            "errorType": (
                payload.get("errorType") or detail.get("errorCode") or detail.get("condition")
            ),
            "errorMessage": payload.get("errorMessage") or detail.get("errorMessage"),
            "detailType": detail_type,
        }
        return lambda_error_incident_key(function_name, error_signature, region)

    if source == "aws.ecs":
        task_arn = detail.get("taskArn") or detail.get("taskArnStr") or "unknown-task"
        cluster = detail.get("clusterArn") or "unknown-cluster"
        reason = detail.get("stoppedReason") or detail.get("stopCode") or "stopped"
        return f"ecs_task:{_region(region)}:{_part(cluster)}:{_part(task_arn)}:{_digest(reason, 8)}"

    if source == "aws.rds":
        resource = detail.get("SourceIdentifier") or detail.get("SourceArn") or "unknown-db"
        categories = detail.get("EventCategories", [])
        message = detail.get("Message") or detail.get("EventMessage") or detail_type
        signature = {"categories": categories, "message": message}
        return f"rds_event:{_region(region)}:{_part(resource)}:{_digest(signature)}"

    if source == "aws.ec2":
        instance_id = detail.get("instance-id") or detail.get("instanceId") or "unknown-instance"
        state = detail.get("state") or detail_type
        return f"ec2_state:{_region(region)}:{_part(instance_id)}:{_part(state)}"

    if source == "aws.codedeploy":
        deployment_id = detail.get("deploymentId") or detail.get("deployment-id") or detail
        return f"codedeploy:{_region(region)}:{_digest(deployment_id)}"

    if source == "aws.guardduty":
        finding_id = detail.get("id") or detail.get("findingId") or detail
        return f"guardduty:{_region(region)}:{_digest(finding_id)}"

    if source == "aws.health":
        event_arn = detail.get("eventArn") or detail.get("eventTypeCode") or detail
        return f"health:{_region(region)}:{_digest(event_arn)}"

    fingerprint = {
        "source": source,
        "detail-type": detail_type,
        "detail": _strip_volatile(detail),
    }
    return f"event:{_part(source)}:{_digest(fingerprint)}"
