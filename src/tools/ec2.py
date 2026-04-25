"""EC2 tool: instance status and system health checks."""

from loguru import logger
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from agent.config import settings



def _ec2_client() -> Any:
    session = boto3.Session(profile_name=settings.aws_profile) if settings.aws_profile else boto3.Session()
    return session.client("ec2", region_name=settings.aws_region)


def describe_ec2_instances(filters: list[dict[str, Any]] | None = None) -> dict:
    """List EC2 instances with their state, type, and tags. Optionally filter by state or tag.

    Args:
        filters: EC2 describe-instances filters, e.g. [{"Name": "instance-state-name", "Values": ["running"]}].
    """
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
        logger.error("describe_ec2_instances failed: {}", e)
        return {"error": str(e), "instances": []}


def get_ec2_system_status(instance_id: str) -> dict:
    """Get EC2 instance status checks (system reachability and instance reachability).

    Args:
        instance_id: EC2 instance ID.
    """
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
        logger.error("get_ec2_system_status failed: {}", e)
        return {"error": str(e)}


ALL_EC2_TOOLS = [describe_ec2_instances, get_ec2_system_status]
