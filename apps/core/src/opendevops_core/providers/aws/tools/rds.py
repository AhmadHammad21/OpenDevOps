"""RDS tool: DB instance status and events."""

from datetime import UTC, datetime, timedelta
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from loguru import logger

from opendevops_core.providers.aws.credentials import get_client
from opendevops_core.tools._cache import tool_cached


def _rds_client() -> Any:
    return get_client("rds")


@tool_cached
def describe_rds_instances() -> dict:
    """List RDS DB instances with their status, engine, class, and multi-AZ configuration."""
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
        logger.error("describe_rds_instances failed: {}", e)
        return {"error": str(e), "instances": []}


@tool_cached
def get_rds_events(hours: int = 24, db_identifier: str | None = None) -> dict:
    """Fetch RDS events log for recent database activity, failovers, maintenance, and errors.

    Args:
        hours: How far back to look. Default 24.
        db_identifier: Filter by specific DB instance identifier. Optional.
    """
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
        logger.error("get_rds_events failed: {}", e)
        return {"error": str(e), "events": []}


ALL_RDS_TOOLS = [describe_rds_instances, get_rds_events]
