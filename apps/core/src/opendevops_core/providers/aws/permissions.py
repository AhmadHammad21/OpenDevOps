"""Permission checker — lightweight read calls to verify AWS access per service."""

from __future__ import annotations

import boto3
from loguru import logger

from opendevops_core.providers.aws.credentials import resolve_region, resolve_session


def _session() -> boto3.Session:
    return resolve_session()


def _check(fn) -> dict:
    try:
        fn()
        return {"passed": True, "error": None}
    except Exception as e:
        return {"passed": False, "error": str(e)}


def _c(s, service: str, region: str):
    return s.client(service, region_name=region)


# Declarative source of truth for the per-service read-permission probe. Each entry is
# (label, boto3 service, read-only operation, kwargs). check_permissions() iterates this,
# and the published tool/permission inventory introspects it — keep them in sync by
# adding probes here only, never by hardcoding calls inline.
PERMISSION_PROBES: tuple[tuple[str, str, str, dict], ...] = (
    ("cloudwatch", "cloudwatch", "describe_alarms", {"MaxRecords": 1}),
    ("cloudtrail", "cloudtrail", "lookup_events", {"MaxResults": 1}),
    ("ecs", "ecs", "list_clusters", {"maxResults": 1}),
    ("lambda", "lambda", "list_functions", {"MaxItems": 1}),
    ("ec2", "ec2", "describe_instances", {"MaxResults": 5}),
    ("rds", "rds", "describe_db_instances", {}),
    ("iam", "sts", "get_caller_identity", {}),
    ("sqs", "sqs", "list_queues", {"MaxResults": 1}),
    ("events", "events", "list_rules", {"Limit": 1}),
)


def check_permissions(region: str | None = None) -> dict[str, dict]:
    """Run one lightweight read call per service. Returns {service: {passed, error}}."""
    s = _session()
    region = region or resolve_region()

    results: dict[str, dict] = {
        label: _check(
            lambda svc=svc, op=op, kwargs=kwargs: getattr(_c(s, svc, region), op)(**kwargs)
        )
        for label, svc, op, kwargs in PERMISSION_PROBES
    }

    for svc, r in results.items():
        status = "✓" if r["passed"] else "✗"
        logger.debug("Permission check {}: {} {}", svc, status, r.get("error") or "")

    return results
