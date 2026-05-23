"""Permission checker — lightweight read calls to verify AWS access per service."""

from __future__ import annotations

import boto3
from loguru import logger

from config import settings


def _session() -> boto3.Session:
    return (
        boto3.Session(profile_name=settings.aws_profile)
        if settings.aws_profile
        else boto3.Session()
    )


def _check(fn) -> dict:
    try:
        fn()
        return {"passed": True, "error": None}
    except Exception as e:
        return {"passed": False, "error": str(e)}


def _c(s, service: str, region: str):
    return s.client(service, region_name=region)


def check_permissions(region: str | None = None) -> dict[str, dict]:
    """Run one lightweight read call per service. Returns {service: {passed, error}}."""
    s = _session()
    region = region or settings.aws_region

    results: dict[str, dict] = {
        "cloudwatch": _check(lambda: _c(s, "cloudwatch", region).describe_alarms(MaxRecords=1)),
        "cloudtrail": _check(lambda: _c(s, "cloudtrail", region).lookup_events(MaxResults=1)),
        "ecs":        _check(lambda: _c(s, "ecs", region).list_clusters(maxResults=1)),
        "lambda":     _check(lambda: _c(s, "lambda", region).list_functions(MaxItems=1)),
        "ec2":        _check(lambda: _c(s, "ec2", region).describe_instances(MaxResults=5)),
        "rds":        _check(lambda: _c(s, "rds", region).describe_db_instances()),
        "iam":        _check(lambda: _c(s, "sts", region).get_caller_identity()),
        "sqs":        _check(lambda: _c(s, "sqs", region).list_queues(MaxResults=1)),
        "events":     _check(lambda: _c(s, "events", region).list_rules(Limit=1)),
    }

    for svc, r in results.items():
        status = "✓" if r["passed"] else "✗"
        logger.debug("Permission check {}: {} {}", svc, status, r.get("error") or "")

    return results
