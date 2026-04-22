"""CloudTrail tool: API audit trail for recent changes."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from agent.config import settings
from tools.base import BaseTool

logger = logging.getLogger(__name__)


def _ct_client() -> Any:
    session = boto3.Session(profile_name=settings.aws_profile) if settings.aws_profile else boto3.Session()
    return session.client("cloudtrail", region_name=settings.aws_region)


class LookupEventsTool(BaseTool):
    name = "lookup_cloudtrail_events"
    description = (
        "Look up recent CloudTrail API events. Useful for finding deployments, config changes, "
        "permission changes, or other actions that preceded an incident."
    )

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "integer",
                        "description": "How far back to look. Default 2.",
                        "default": 2,
                    },
                    "resource_name": {
                        "type": "string",
                        "description": "Filter by resource name (e.g. Lambda function name). Optional.",
                    },
                    "event_name": {
                        "type": "string",
                        "description": "Filter by API event name (e.g. UpdateFunctionCode). Optional.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max events to return. Default 50.",
                        "default": 50,
                    },
                },
                "required": [],
            },
        }

    def run(
        self,
        hours: int = 2,
        resource_name: str | None = None,
        event_name: str | None = None,
        limit: int = 50,
        **_: Any,
    ) -> dict[str, Any]:
        try:
            client = _ct_client()
            start = datetime.now(UTC) - timedelta(hours=hours)
            end = datetime.now(UTC)

            kwargs: dict[str, Any] = {
                "StartTime": start,
                "EndTime": end,
                "MaxResults": min(limit, 50),
            }
            if resource_name:
                kwargs["LookupAttributes"] = [{"AttributeKey": "ResourceName", "AttributeValue": resource_name}]
            elif event_name:
                kwargs["LookupAttributes"] = [{"AttributeKey": "EventName", "AttributeValue": event_name}]

            resp = client.lookup_events(**kwargs)
            events = []
            for event in resp.get("Events", [])[:limit]:
                resources = [
                    {"type": r.get("ResourceType", ""), "name": r.get("ResourceName", "")}
                    for r in event.get("Resources", [])
                ]
                events.append(
                    {
                        "event_name": event.get("EventName", ""),
                        "event_time": event["EventTime"].isoformat() if event.get("EventTime") else "",
                        "username": event.get("Username", ""),
                        "resources": resources,
                        "event_id": event.get("EventId", ""),
                    }
                )
            return {"events": events, "count": len(events)}
        except (BotoCoreError, ClientError) as e:
            logger.error("lookup_cloudtrail_events failed: %s", e)
            return {"error": str(e), "events": []}


ALL_CLOUDTRAIL_TOOLS: list[BaseTool] = [LookupEventsTool()]
