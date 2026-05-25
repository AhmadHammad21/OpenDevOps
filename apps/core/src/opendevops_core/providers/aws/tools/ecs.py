"""ECS tool: services, tasks, and task logs."""

from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from loguru import logger

from opendevops_core.providers.aws.credentials import get_client
from opendevops_core.tools._cache import tool_cached


def _ecs_client() -> Any:
    return get_client("ecs")


def _logs_client() -> Any:
    return get_client("logs")


@tool_cached
def list_ecs_clusters() -> dict:
    """List all ECS clusters in the region with their status and active service/task counts."""
    try:
        client = _ecs_client()
        paginator = client.get_paginator("list_clusters")
        arns: list[str] = []
        for page in paginator.paginate():
            arns.extend(page.get("clusterArns", []))

        if not arns:
            return {"clusters": [], "count": 0}

        clusters = []
        for i in range(0, len(arns), 100):
            resp = client.describe_clusters(clusters=arns[i : i + 100])
            for c in resp.get("clusters", []):
                clusters.append(
                    {
                        "name": c["clusterName"],
                        "arn": c["clusterArn"],
                        "status": c.get("status", ""),
                        "active_services": c.get("activeServicesCount", 0),
                        "running_tasks": c.get("runningTasksCount", 0),
                        "pending_tasks": c.get("pendingTasksCount", 0),
                    }
                )
        return {"clusters": clusters, "count": len(clusters)}
    except (BotoCoreError, ClientError) as e:
        logger.error("list_ecs_clusters failed: {}", e)
        return {"error": str(e), "clusters": []}


@tool_cached
def list_ecs_services(cluster: str) -> dict:
    """List ECS services in a cluster with their desired, running, and pending task counts.

    Args:
        cluster: ECS cluster name or ARN.
    """
    try:
        client = _ecs_client()
        paginator = client.get_paginator("list_services")
        arns = []
        for page in paginator.paginate(cluster=cluster):
            arns.extend(page.get("serviceArns", []))

        if not arns:
            return {"cluster": cluster, "services": [], "count": 0}

        services = []
        for i in range(0, len(arns), 10):
            resp = client.describe_services(cluster=cluster, services=arns[i : i + 10])
            for svc in resp.get("services", []):
                services.append(
                    {
                        "name": svc["serviceName"],
                        "status": svc["status"],
                        "desired": svc["desiredCount"],
                        "running": svc["runningCount"],
                        "pending": svc["pendingCount"],
                        "task_definition": svc.get("taskDefinition", "").split("/")[-1],
                    }
                )
        return {"cluster": cluster, "services": services, "count": len(services)}
    except (BotoCoreError, ClientError) as e:
        logger.error("list_ecs_services failed: {}", e)
        return {"error": str(e), "services": []}


@tool_cached
def describe_ecs_service(cluster: str, service: str) -> dict:
    """Get detailed info about an ECS service including recent events and deployment status.

    Args:
        cluster: ECS cluster name or ARN.
        service: ECS service name or ARN.
    """
    try:
        client = _ecs_client()
        resp = client.describe_services(cluster=cluster, services=[service])
        services = resp.get("services", [])
        if not services:
            return {"error": f"Service '{service}' not found in cluster '{cluster}'"}

        svc = services[0]
        events = [
            {"created_at": e["createdAt"].isoformat(), "message": e["message"]}
            for e in svc.get("events", [])[:20]
        ]
        deployments = [
            {
                "status": d["status"],
                "desired": d["desiredCount"],
                "running": d["runningCount"],
                "failed": d["failedTasks"],
                "created_at": d["createdAt"].isoformat(),
                "task_definition": d.get("taskDefinition", "").split("/")[-1],
            }
            for d in svc.get("deployments", [])
        ]
        return {
            "name": svc["serviceName"],
            "status": svc["status"],
            "desired": svc["desiredCount"],
            "running": svc["runningCount"],
            "pending": svc["pendingCount"],
            "deployments": deployments,
            "events": events,
        }
    except (BotoCoreError, ClientError) as e:
        logger.error("describe_ecs_service failed: {}", e)
        return {"error": str(e)}


@tool_cached
def get_ecs_task_logs(cluster: str, task_id: str, log_group: str, limit: int = 100) -> dict:
    """Fetch stdout/stderr logs for a specific ECS task from CloudWatch Logs.

    Args:
        cluster: ECS cluster name.
        task_id: ECS task ID (short or full ARN).
        log_group: CloudWatch log group for the task. Often /ecs/<service-name>.
        limit: Max log lines. Default 100.
    """
    try:
        short_id = task_id.split("/")[-1]
        client = _logs_client()
        resp = client.filter_log_events(
            logGroupName=log_group,
            logStreamNames=[f"ecs/{cluster}/{short_id}"],
            limit=limit,
        )
        events = [{"message": e["message"].strip()} for e in resp.get("events", [])]
        return {"task_id": short_id, "log_group": log_group, "events": events, "count": len(events)}
    except (BotoCoreError, ClientError) as e:
        logger.error("get_ecs_task_logs failed: {}", e)
        return {"error": str(e), "events": []}


ALL_ECS_TOOLS = [list_ecs_clusters, list_ecs_services, describe_ecs_service, get_ecs_task_logs]
