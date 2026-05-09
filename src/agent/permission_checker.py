"""Permission checker — lightweight read calls to verify AWS access per service."""

from __future__ import annotations

import boto3
from loguru import logger

from config import settings


def _session() -> boto3.Session:
    return boto3.Session(profile_name=settings.aws_profile) if settings.aws_profile else boto3.Session()


def _check(fn) -> dict:
    try:
        fn()
        return {"passed": True, "error": None}
    except Exception as e:
        return {"passed": False, "error": str(e)}


def check_permissions(sns_topic_arn: str = "") -> dict[str, dict]:
    """Run one lightweight read call per service. Returns {service: {passed, error}}."""
    s = _session()
    region = settings.aws_region

    results: dict[str, dict] = {}

    results["cloudwatch"] = _check(lambda: s.client("cloudwatch", region_name=region).describe_alarms(MaxRecords=1))
    results["cloudtrail"] = _check(lambda: s.client("cloudtrail", region_name=region).lookup_events(MaxResults=1))
    results["ecs"] = _check(lambda: s.client("ecs", region_name=region).list_clusters(maxResults=1))
    results["lambda"] = _check(lambda: s.client("lambda", region_name=region).list_functions(MaxItems=1))
    results["ec2"] = _check(lambda: s.client("ec2", region_name=region).describe_instances(MaxResults=5))
    results["rds"] = _check(lambda: s.client("rds", region_name=region).describe_db_instances())
    results["iam"] = _check(lambda: s.client("sts", region_name=region).get_caller_identity())

    if sns_topic_arn:
        results["sns"] = _check(
            lambda: s.client("sns", region_name=region).get_topic_attributes(TopicArn=sns_topic_arn)
        )
    else:
        results["sns"] = {"passed": None, "error": "No SNS topic ARN provided"}

    results["sqs"] = _check(lambda: s.client("sqs", region_name=region).list_queues(MaxResults=1))
    results["events"] = _check(lambda: s.client("events", region_name=region).list_rules(Limit=1))

    for svc, r in results.items():
        status = "✓" if r["passed"] else ("?" if r["passed"] is None else "✗")
        logger.debug("Permission check {}: {} {}", svc, status, r.get("error") or "")

    return results
