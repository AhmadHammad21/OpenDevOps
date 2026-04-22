"""CloudWatch tool: alarms, metrics, and log events."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from agent.config import settings
from tools.base import BaseTool

logger = logging.getLogger(__name__)


def _cw_client() -> Any:
    session = boto3.Session(profile_name=settings.aws_profile) if settings.aws_profile else boto3.Session()
    return session.client("cloudwatch", region_name=settings.aws_region)


def _logs_client() -> Any:
    session = boto3.Session(profile_name=settings.aws_profile) if settings.aws_profile else boto3.Session()
    return session.client("logs", region_name=settings.aws_region)


class GetAlarmsTool(BaseTool):
    name = "get_alarms"
    description = "List CloudWatch alarms, optionally filtered by state (OK, ALARM, INSUFFICIENT_DATA)."

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "enum": ["OK", "ALARM", "INSUFFICIENT_DATA"],
                        "description": "Filter alarms by state. Omit to return all alarms.",
                    }
                },
                "required": [],
            },
        }

    def run(self, state: str | None = None, **_: Any) -> dict[str, Any]:
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
            logger.error("get_alarms failed: %s", e)
            return {"error": str(e), "alarms": []}


class GetAlarmHistoryTool(BaseTool):
    name = "get_alarm_history"
    description = "Fetch state-change history for a specific CloudWatch alarm."

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "alarm_name": {"type": "string", "description": "Name of the CloudWatch alarm."},
                    "hours": {
                        "type": "integer",
                        "description": "How many hours back to look. Default 24.",
                        "default": 24,
                    },
                },
                "required": ["alarm_name"],
            },
        }

    def run(self, alarm_name: str, hours: int = 24, **_: Any) -> dict[str, Any]:
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
            logger.error("get_alarm_history failed: %s", e)
            return {"error": str(e), "history": []}


class GetMetricDataTool(BaseTool):
    name = "get_metric_data"
    description = "Fetch raw CloudWatch metric data points for a given namespace/metric/dimensions."

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string", "description": "e.g. AWS/Lambda"},
                    "metric": {"type": "string", "description": "e.g. Errors"},
                    "dimensions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "Name": {"type": "string"},
                                "Value": {"type": "string"},
                            },
                        },
                        "description": "List of dimension name/value pairs.",
                    },
                    "period": {"type": "integer", "description": "Period in seconds. Default 300.", "default": 300},
                    "hours": {"type": "integer", "description": "How far back to look. Default 3.", "default": 3},
                    "stat": {
                        "type": "string",
                        "description": "Statistic: Sum, Average, Maximum. Default Sum.",
                        "default": "Sum",
                    },
                },
                "required": ["namespace", "metric", "dimensions"],
            },
        }

    def run(
        self,
        namespace: str,
        metric: str,
        dimensions: list[dict[str, str]],
        period: int = 300,
        hours: int = 3,
        stat: str = "Sum",
        **_: Any,
    ) -> dict[str, Any]:
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
                [{"timestamp": dp["Timestamp"].isoformat(), "value": dp[stat]} for dp in resp.get("Datapoints", [])],
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
            logger.error("get_metric_data failed: %s", e)
            return {"error": str(e), "datapoints": []}


class GetLogEventsTool(BaseTool):
    name = "get_log_events"
    description = "Fetch recent log events from a CloudWatch Logs log group, with optional filter pattern."

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "log_group": {"type": "string", "description": "CloudWatch log group name."},
                    "log_stream": {"type": "string", "description": "Specific log stream. Optional."},
                    "filter_pattern": {
                        "type": "string",
                        "description": "CloudWatch filter pattern, e.g. 'ERROR'. Optional.",
                    },
                    "hours": {"type": "integer", "description": "How far back to look. Default 1.", "default": 1},
                    "limit": {"type": "integer", "description": "Max events to return. Default 100.", "default": 100},
                },
                "required": ["log_group"],
            },
        }

    def run(
        self,
        log_group: str,
        log_stream: str | None = None,
        filter_pattern: str | None = None,
        hours: int = 1,
        limit: int = 100,
        **_: Any,
    ) -> dict[str, Any]:
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
            logger.error("get_log_events failed: %s", e)
            return {"error": str(e), "events": []}


class DescribeLogGroupsTool(BaseTool):
    name = "describe_log_groups"
    description = "List CloudWatch log groups, optionally filtered by name prefix."

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "prefix": {"type": "string", "description": "Filter log groups by name prefix. Optional."}
                },
                "required": [],
            },
        }

    def run(self, prefix: str | None = None, **_: Any) -> dict[str, Any]:
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
            logger.error("describe_log_groups failed: %s", e)
            return {"error": str(e), "log_groups": []}


ALL_CLOUDWATCH_TOOLS: list[BaseTool] = [
    GetAlarmsTool(),
    GetAlarmHistoryTool(),
    GetMetricDataTool(),
    GetLogEventsTool(),
    DescribeLogGroupsTool(),
]
