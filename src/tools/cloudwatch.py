"""CloudWatch tool: alarms, metrics, and log events."""

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from loguru import logger

from agent.init_store import get_runtime_aws_region
from config import settings
from tools._cache import tool_cached


def _cw_client() -> Any:
    session = (
        boto3.Session(profile_name=settings.aws_profile)
        if settings.aws_profile
        else boto3.Session()
    )
    return session.client("cloudwatch", region_name=get_runtime_aws_region())


def _logs_client() -> Any:
    session = (
        boto3.Session(profile_name=settings.aws_profile)
        if settings.aws_profile
        else boto3.Session()
    )
    return session.client("logs", region_name=get_runtime_aws_region())


@tool_cached
def get_alarms(state: str | None = None) -> dict:
    """List CloudWatch alarms, optionally filtered by state (OK, ALARM, INSUFFICIENT_DATA)."""
    try:
        client = _cw_client()
        kwargs: dict[str, Any] = {}
        if state:
            kwargs["StateValue"] = state
        paginator = client.get_paginator("describe_alarms")
        alarms = []
        for page in paginator.paginate(**kwargs):
            for alarm in page.get("MetricAlarms", []):
                alarms.append(
                    {
                        "name": alarm["AlarmName"],
                        "state": alarm["StateValue"],
                        "reason": alarm.get("StateReason", ""),
                        "metric": alarm.get("MetricName", ""),
                        "namespace": alarm.get("Namespace", ""),
                        "updated_at": alarm["StateUpdatedTimestamp"].isoformat()
                        if alarm.get("StateUpdatedTimestamp")
                        else "",
                    }
                )
        return {"alarms": alarms, "count": len(alarms)}
    except (BotoCoreError, ClientError) as e:
        logger.error("get_alarms failed: {}", e)
        return {"error": str(e), "alarms": []}


@tool_cached
def get_alarm_history(alarm_name: str, hours: int = 24) -> dict:
    """Fetch state-change history for a specific CloudWatch alarm.

    Args:
        alarm_name: Name of the CloudWatch alarm.
        hours: How many hours back to look. Default 24.
    """
    try:
        client = _cw_client()
        start = datetime.now(UTC) - timedelta(hours=hours)
        resp = client.describe_alarm_history(
            AlarmName=alarm_name,
            HistoryItemType="StateUpdate",
            StartDate=start,
            EndDate=datetime.now(UTC),
        )
        history = [
            {
                "timestamp": item["Timestamp"].isoformat(),
                "summary": item.get("HistorySummary", ""),
            }
            for item in resp.get("AlarmHistoryItems", [])
        ]
        return {"alarm_name": alarm_name, "history": history, "count": len(history)}
    except (BotoCoreError, ClientError, NotImplementedError) as e:
        logger.error("get_alarm_history failed: {}", e)
        return {"error": str(e), "history": []}


@tool_cached
def get_metric_data(
    namespace: str,
    metric: str,
    dimensions: list[dict[str, str]],
    period: int = 300,
    hours: int = 3,
    stat: str = "Sum",
) -> dict:
    """Fetch raw CloudWatch metric data points for a given namespace/metric/dimensions.

    Args:
        namespace: e.g. AWS/Lambda
        metric: e.g. Errors
        dimensions: List of {Name, Value} pairs e.g. [{"Name": "FunctionName", "Value": "my-fn"}]
        period: Period in seconds. Default 300.
        hours: How far back to look. Default 3.
        stat: Statistic: Sum, Average, Maximum. Default Sum.
    """
    try:
        client = _cw_client()
        end = datetime.now(UTC)
        start = end - timedelta(hours=hours)
        resp = client.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric,
            Dimensions=dimensions,
            StartTime=start,
            EndTime=end,
            Period=period,
            Statistics=[stat],
        )
        datapoints = sorted(
            [
                {"timestamp": dp["Timestamp"].isoformat(), "value": dp[stat]}
                for dp in resp.get("Datapoints", [])
            ],
            key=lambda x: x["timestamp"],
        )
        return {
            "namespace": namespace,
            "metric": metric,
            "stat": stat,
            "datapoints": datapoints,
            "count": len(datapoints),
        }
    except (BotoCoreError, ClientError) as e:
        logger.error("get_metric_data failed: {}", e)
        return {"error": str(e), "datapoints": []}


@tool_cached
def get_log_events(
    log_group: str,
    log_stream: str | None = None,
    filter_pattern: str | None = None,
    hours: int = 1,
    limit: int = 100,
) -> dict:
    """Fetch recent log events from a CloudWatch Logs group, with optional filter pattern.

    Args:
        log_group: CloudWatch log group name.
        log_stream: Specific log stream. Optional.
        filter_pattern: CloudWatch filter pattern, e.g. 'ERROR'. Optional.
        hours: How far back to look. Default 1.
        limit: Max events to return. Default 100.
    """
    try:
        client = _logs_client()
        start_ms = int((datetime.now(UTC) - timedelta(hours=hours)).timestamp() * 1000)
        end_ms = int(datetime.now(UTC).timestamp() * 1000)

        kwargs: dict[str, Any] = {
            "logGroupName": log_group,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": limit,
        }
        if log_stream:
            kwargs["logStreamNames"] = [log_stream]
        if filter_pattern:
            kwargs["filterPattern"] = filter_pattern

        resp = client.filter_log_events(**kwargs)
        events = [
            {
                "timestamp": datetime.fromtimestamp(e["timestamp"] / 1000, UTC).isoformat(),
                "message": e["message"].strip(),
                "stream": e.get("logStreamName", ""),
            }
            for e in resp.get("events", [])
        ]
        return {"log_group": log_group, "events": events, "count": len(events)}
    except (BotoCoreError, ClientError) as e:
        logger.error("get_log_events failed: {}", e)
        return {"error": str(e), "events": []}


@tool_cached
def describe_log_groups(prefix: str | None = None) -> dict:
    """List CloudWatch log groups, optionally filtered by name prefix.

    Args:
        prefix: Filter log groups by name prefix. Optional.
    """
    try:
        client = _logs_client()
        kwargs: dict[str, Any] = {}
        if prefix:
            kwargs["logGroupNamePrefix"] = prefix
        paginator = client.get_paginator("describe_log_groups")
        groups = []
        for page in paginator.paginate(**kwargs):
            for group in page.get("logGroups", []):
                groups.append(
                    {
                        "name": group["logGroupName"],
                        "retention_days": group.get("retentionInDays"),
                        "stored_bytes": group.get("storedBytes", 0),
                    }
                )
        return {"log_groups": groups, "count": len(groups)}
    except (BotoCoreError, ClientError) as e:
        logger.error("describe_log_groups failed: {}", e)
        return {"error": str(e), "log_groups": []}


@tool_cached
def query_logs_insights(
    log_group: str,
    query: str,
    hours: int = 1,
    limit: int = 100,
) -> dict:
    """Run a CloudWatch Logs Insights structured query against a log group.

    Supports the full Logs Insights query language: fields, filter, stats, sort, limit.
    Example queries:
            - 'fields @timestamp, @message | filter @message like /ERROR/ | limit 50'
      - 'stats count(*) as errors by bin(5m) | sort errors desc'
      - 'fields @timestamp, @message | filter @message like /WARN/ | limit 100'

    Args:
        log_group: CloudWatch log group name (e.g. /aws/lambda/my-fn).
        query: Logs Insights query string.
        hours: Time window to search. Default 1.
        limit: Max results to return. Default 100.
    """
    try:
        client = _logs_client()
        end_ts = int(datetime.now(UTC).timestamp())
        start_ts = int((datetime.now(UTC) - timedelta(hours=hours)).timestamp())

        resp = client.start_query(
            logGroupName=log_group,
            startTime=start_ts,
            endTime=end_ts,
            queryString=query,
            limit=limit,
        )
        query_id = resp["queryId"]

        # Poll until complete — real AWS takes 1–30s; moto returns Complete immediately
        deadline = time.time() + 30
        status = ""
        result_resp: dict = {}
        while time.time() < deadline:
            result_resp = client.get_query_results(queryId=query_id)
            status = result_resp.get("status", "")
            if status in ("Complete", "Failed", "Cancelled", "Timeout"):
                break
            time.sleep(1)

        if status != "Complete":
            return {"error": f"Query ended with status: {status}", "results": []}

        rows = [
            {field["field"]: field["value"] for field in record}
            for record in result_resp.get("results", [])[:limit]
        ]
        stats = result_resp.get("statistics", {})
        return {
            "log_group": log_group,
            "query": query,
            "results": rows,
            "count": len(rows),
            "scanned_mb": round(stats.get("bytesScanned", 0) / 1e6, 3),
        }
    except (BotoCoreError, ClientError) as e:
        logger.error("query_logs_insights failed: {}", e)
        return {"error": str(e), "results": []}


ALL_CLOUDWATCH_TOOLS = [
    get_alarms,
    get_alarm_history,
    get_metric_data,
    get_log_events,
    describe_log_groups,
    query_logs_insights,
]
