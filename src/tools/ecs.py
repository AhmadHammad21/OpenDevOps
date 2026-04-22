"""ECS tool: services, tasks, and task logs."""

import logging
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from agent.config import settings
from tools.base import BaseTool

logger = logging.getLogger(__name__)


def _ecs_client() -> Any:
    session = boto3.Session(profile_name=settings.aws_profile) if settings.aws_profile else boto3.Session()
    return session.client("ecs", region_name=settings.aws_region)


def _logs_client() -> Any:
    session = boto3.Session(profile_name=settings.aws_profile) if settings.aws_profile else boto3.Session()
    return session.client("logs", region_name=settings.aws_region)


class ListServicesTool(BaseTool):
    name = "list_ecs_services"
    description = "List ECS services in a cluster with their desired/running/pending counts and status."

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "cluster": {"type": "string", "description": "ECS cluster name or ARN."}
                },
                "required": ["cluster"],
            },
        }

    def run(self, cluster: str, **_: Any) -> dict[str, Any]:
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
            logger.error("list_ecs_services failed: %s", e)
            return {"error": str(e), "services": []}


class DescribeServiceTool(BaseTool):
    name = "describe_ecs_service"
    description = "Get detailed info about a specific ECS service including recent events and deployment status."

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "cluster": {"type": "string", "description": "ECS cluster name or ARN."},
                    "service": {"type": "string", "description": "ECS service name or ARN."},
                },
                "required": ["cluster", "service"],
            },
        }

    def run(self, cluster: str, service: str, **_: Any) -> dict[str, Any]:
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
            logger.error("describe_ecs_service failed: %s", e)
            return {"error": str(e)}


class GetTaskLogsTool(BaseTool):
    name = "get_ecs_task_logs"
    description = "Fetch stdout/stderr logs for a specific ECS task from CloudWatch Logs."

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "cluster": {"type": "string", "description": "ECS cluster name."},
                    "task_id": {"type": "string", "description": "ECS task ID (short or full ARN)."},
                    "log_group": {
                        "type": "string",
                        "description": "CloudWatch log group for the task. Often /ecs/<service-name>.",
                    },
                    "limit": {"type": "integer", "description": "Max log lines. Default 100.", "default": 100},
                },
                "required": ["cluster", "task_id", "log_group"],
            },
        }

    def run(self, cluster: str, task_id: str, log_group: str, limit: int = 100, **_: Any) -> dict[str, Any]:
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
            logger.error("get_ecs_task_logs failed: %s", e)
            return {"error": str(e), "events": []}


ALL_ECS_TOOLS: list[BaseTool] = [ListServicesTool(), DescribeServiceTool(), GetTaskLogsTool()]
