"""EC2 tool: instance status and system health checks."""

import logging
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from agent.config import settings
from tools.base import BaseTool

logger = logging.getLogger(__name__)


def _ec2_client() -> Any:
    session = boto3.Session(profile_name=settings.aws_profile) if settings.aws_profile else boto3.Session()
    return session.client("ec2", region_name=settings.aws_region)


class DescribeInstancesTool(BaseTool):
    name = "describe_ec2_instances"
    description = "List EC2 instances with their state, type, and tags. Optionally filter by state or tag."

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "Name": {"type": "string"},
                                "Values": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                        "description": "EC2 describe-instances filters. e.g. [{Name: 'instance-state-name', Values: ['running']}]",
                    }
                },
                "required": [],
            },
        }

    def run(self, filters: list[dict[str, Any]] | None = None, **_: Any) -> dict[str, Any]:
        try:
            client = _ec2_client()
            kwargs: dict[str, Any] = {}
            if filters:
                kwargs["Filters"] = filters
            paginator = client.get_paginator("describe_instances")
            instances = []
            for page in paginator.paginate(**kwargs):
                for reservation in page.get("Reservations", []):
                    for inst in reservation.get("Instances", []):
                        name_tag = next(
                            (t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"), ""
                        )
                        instances.append(
                            {
                                "instance_id": inst["InstanceId"],
                                "name": name_tag,
                                "type": inst.get("InstanceType", ""),
                                "state": inst["State"]["Name"],
                                "az": inst.get("Placement", {}).get("AvailabilityZone", ""),
                                "private_ip": inst.get("PrivateIpAddress", ""),
                                "launch_time": inst.get("LaunchTime", "").isoformat()
                                if inst.get("LaunchTime")
                                else "",
                            }
                        )
            return {"instances": instances, "count": len(instances)}
        except (BotoCoreError, ClientError) as e:
            logger.error("describe_ec2_instances failed: %s", e)
            return {"error": str(e), "instances": []}


class GetSystemStatusTool(BaseTool):
    name = "get_ec2_system_status"
    description = "Get EC2 instance status checks (system reachability, instance reachability) for a specific instance."

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "instance_id": {"type": "string", "description": "EC2 instance ID."}
                },
                "required": ["instance_id"],
            },
        }

    def run(self, instance_id: str, **_: Any) -> dict[str, Any]:
        try:
            client = _ec2_client()
            resp = client.describe_instance_status(InstanceIds=[instance_id], IncludeAllInstances=True)
            statuses = resp.get("InstanceStatuses", [])
            if not statuses:
                return {"error": f"Instance {instance_id} not found"}

            s = statuses[0]
            return {
                "instance_id": instance_id,
                "instance_state": s["InstanceState"]["Name"],
                "system_status": s.get("SystemStatus", {}).get("Status", ""),
                "instance_status": s.get("InstanceStatus", {}).get("Status", ""),
                "system_events": [
                    {"code": e.get("Code", ""), "description": e.get("Description", "")}
                    for e in s.get("Events", [])
                ],
            }
        except (BotoCoreError, ClientError) as e:
            logger.error("get_ec2_system_status failed: %s", e)
            return {"error": str(e)}


ALL_EC2_TOOLS: list[BaseTool] = [DescribeInstancesTool(), GetSystemStatusTool()]
