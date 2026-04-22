"""RDS tool: DB instance status and events."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from agent.config import settings
from tools.base import BaseTool

logger = logging.getLogger(__name__)


def _rds_client() -> Any:
    session = boto3.Session(profile_name=settings.aws_profile) if settings.aws_profile else boto3.Session()
    return session.client("rds", region_name=settings.aws_region)


class DescribeDBInstancesTool(BaseTool):
    name = "describe_rds_instances"
    description = "List RDS DB instances with their status, engine, class, and multi-AZ configuration."

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    def run(self, **_: Any) -> dict[str, Any]:
        try:
            client = _rds_client()
            paginator = client.get_paginator("describe_db_instances")
            instances = []
            for page in paginator.paginate():
                for db in page.get("DBInstances", []):
                    instances.append(
                        {
                            "identifier": db["DBInstanceIdentifier"],
                            "status": db["DBInstanceStatus"],
                            "engine": f"{db.get('Engine', '')} {db.get('EngineVersion', '')}".strip(),
                            "class": db.get("DBInstanceClass", ""),
                            "multi_az": db.get("MultiAZ", False),
                            "storage_gb": db.get("AllocatedStorage", 0),
                            "endpoint": db.get("Endpoint", {}).get("Address", ""),
                        }
                    )
            return {"instances": instances, "count": len(instances)}
        except (BotoCoreError, ClientError) as e:
            logger.error("describe_rds_instances failed: %s", e)
            return {"error": str(e), "instances": []}


class GetDBEventsTool(BaseTool):
    name = "get_rds_events"
    description = "Fetch RDS events log for recent database activity, failovers, maintenance, and errors."

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "hours": {"type": "integer", "description": "How far back to look. Default 24.", "default": 24},
                    "db_identifier": {
                        "type": "string",
                        "description": "Filter by specific DB instance identifier. Optional.",
                    },
                },
                "required": [],
            },
        }

    def run(self, hours: int = 24, db_identifier: str | None = None, **_: Any) -> dict[str, Any]:
        try:
            client = _rds_client()
            start = datetime.now(UTC) - timedelta(hours=hours)
            kwargs: dict[str, Any] = {"StartTime": start, "Duration": min(hours * 60, 20160)}
            if db_identifier:
                kwargs["SourceIdentifier"] = db_identifier
                kwargs["SourceType"] = "db-instance"

            paginator = client.get_paginator("describe_events")
            events = []
            for page in paginator.paginate(**kwargs):
                for event in page.get("Events", []):
                    events.append(
                        {
                            "source": event.get("SourceIdentifier", ""),
                            "message": event.get("Message", ""),
                            "date": event["Date"].isoformat() if event.get("Date") else "",
                            "categories": event.get("EventCategories", []),
                        }
                    )
            return {"events": events, "count": len(events)}
        except (BotoCoreError, ClientError) as e:
            logger.error("get_rds_events failed: %s", e)
            return {"error": str(e), "events": []}


ALL_RDS_TOOLS: list[BaseTool] = [DescribeDBInstancesTool(), GetDBEventsTool()]
