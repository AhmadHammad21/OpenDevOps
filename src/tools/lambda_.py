"""Lambda tool: function config, errors, and throttles."""

from loguru import logger
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from agent.config import settings



def _lambda_client() -> Any:
    session = boto3.Session(profile_name=settings.aws_profile) if settings.aws_profile else boto3.Session()
    return session.client("lambda", region_name=settings.aws_region)


def _cw_client() -> Any:
    session = boto3.Session(profile_name=settings.aws_profile) if settings.aws_profile else boto3.Session()
    return session.client("cloudwatch", region_name=settings.aws_region)


def list_lambda_functions() -> dict:
    """List all Lambda functions in the region with their runtime, memory, and timeout."""
    try:
        client = _lambda_client()
        paginator = client.get_paginator("list_functions")
        functions = []
        for page in paginator.paginate():
            for fn in page.get("Functions", []):
                functions.append(
                    {
                        "name": fn["FunctionName"],
                        "runtime": fn.get("Runtime", ""),
                        "memory_mb": fn.get("MemorySize", 0),
                        "timeout_s": fn.get("Timeout", 0),
                        "last_modified": fn.get("LastModified", ""),
                    }
                )
        return {"functions": functions, "count": len(functions)}
    except (BotoCoreError, ClientError) as e:
        logger.error("list_lambda_functions failed: {}", e)
        return {"error": str(e), "functions": []}


def get_lambda_function_config(name: str) -> dict:
    """Get detailed configuration for a Lambda function: memory, timeout, env vars, layers, VPC.

    Args:
        name: Lambda function name.
    """
    try:
        client = _lambda_client()
        resp = client.get_function_configuration(FunctionName=name)
        env_var_keys = list(resp.get("Environment", {}).get("Variables", {}).keys())
        vpc = resp.get("VpcConfig", {})
        return {
            "name": resp["FunctionName"],
            "runtime": resp.get("Runtime", ""),
            "memory_mb": resp.get("MemorySize", 0),
            "timeout_s": resp.get("Timeout", 0),
            "last_modified": resp.get("LastModified", ""),
            "env_var_keys": env_var_keys,
            "layers": [layer["Arn"].split(":")[-2] for layer in resp.get("Layers", [])],
            "vpc_enabled": bool(vpc.get("VpcId")),
            "reserved_concurrency": resp.get("ReservedConcurrentExecutions"),
        }
    except (BotoCoreError, ClientError) as e:
        logger.error("get_lambda_function_config failed: {}", e)
        return {"error": str(e)}


def get_lambda_error_rate(name: str, hours: int = 3) -> dict:
    """Get Lambda error count and throttle count from CloudWatch for a given time window.

    Args:
        name: Lambda function name.
        hours: How far back to look. Default 3.
    """
    try:
        client = _cw_client()
        end = datetime.now(UTC)
        start = end - timedelta(hours=hours)
        dims = [{"Name": "FunctionName", "Value": name}]

        def _get_sum(metric: str) -> list[dict[str, Any]]:
            resp = client.get_metric_statistics(
                Namespace="AWS/Lambda",
                MetricName=metric,
                Dimensions=dims,
                StartTime=start,
                EndTime=end,
                Period=300,
                Statistics=["Sum"],
            )
            return sorted(
                [{"timestamp": dp["Timestamp"].isoformat(), "value": dp["Sum"]} for dp in resp.get("Datapoints", [])],
                key=lambda x: x["timestamp"],
            )

        errors = _get_sum("Errors")
        throttles = _get_sum("Throttles")
        invocations = _get_sum("Invocations")

        total_errors = sum(dp["value"] for dp in errors)
        total_throttles = sum(dp["value"] for dp in throttles)
        total_invocations = sum(dp["value"] for dp in invocations)

        return {
            "function": name,
            "hours": hours,
            "total_invocations": total_invocations,
            "total_errors": total_errors,
            "total_throttles": total_throttles,
            "error_rate_pct": round(total_errors / total_invocations * 100, 2) if total_invocations else 0,
            "errors_by_period": errors,
            "throttles_by_period": throttles,
        }
    except (BotoCoreError, ClientError) as e:
        logger.error("get_lambda_error_rate failed: {}", e)
        return {"error": str(e)}


ALL_LAMBDA_TOOLS = [list_lambda_functions, get_lambda_function_config, get_lambda_error_rate]
