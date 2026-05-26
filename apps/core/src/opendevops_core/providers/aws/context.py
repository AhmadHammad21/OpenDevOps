"""Per-event-type context collectors — deterministic boto3 calls, no LLM."""

from __future__ import annotations

from typing import Any

import boto3
from loguru import logger

from opendevops_core.agent.init_store import get_runtime_aws_region
from opendevops_core.providers.aws.credentials import resolve_session


def _session() -> boto3.Session:
    return resolve_session()


def collect_context(event: dict) -> dict[str, Any]:
    """Dispatch to the right collector based on event source/detail-type."""
    source = event.get("source", "")
    detail_type = event.get("detail-type", "")
    detail = event.get("detail", {})

    try:
        if source == "aws.cloudwatch":
            return _collect_alarm(detail)
        elif source == "aws.lambda":
            return _collect_lambda(detail)
        elif source == "aws.ecs":
            return _collect_ecs(detail)
        elif source == "aws.ec2":
            return _collect_ec2(detail)
        elif source == "aws.rds":
            return _collect_rds(detail)
        elif source == "aws.health":
            return {"type": "health", "detail": detail}
        elif source == "aws.codedeploy":
            return _collect_codedeploy(detail)
        elif source == "aws.guardduty":
            return {"type": "guardduty", "detail": detail}
        else:
            return {
                "type": "unknown",
                "source": source,
                "detail_type": detail_type,
                "detail": detail,
            }
    except Exception as e:
        logger.error("Context collection failed for {}/{}: {}", source, detail_type, e)
        return {"type": source, "error": str(e), "detail": detail}


def _collect_alarm(detail: dict) -> dict:
    """Collect context for a CloudWatch alarm state change."""
    import datetime

    s = _session()
    region = get_runtime_aws_region()
    cw = s.client("cloudwatch", region_name=region)

    alarm_name = detail.get("alarmName", "")
    ctx: dict[str, Any] = {"type": "alarm", "alarm_name": alarm_name, "detail": detail}

    resp = cw.describe_alarms(AlarmNames=[alarm_name])
    alarms = resp.get("MetricAlarms", []) + resp.get("CompositeAlarms", [])
    if alarms:
        alarm = alarms[0]
        ctx["metric_name"] = alarm.get("MetricName", "")
        ctx["namespace"] = alarm.get("Namespace", "")
        ctx["threshold"] = alarm.get("Threshold")
        ctx["dimensions"] = alarm.get("Dimensions", [])

        end = datetime.datetime.now(datetime.UTC)
        start = end - datetime.timedelta(hours=1)
        try:
            metric_resp = cw.get_metric_data(
                MetricDataQueries=[
                    {
                        "Id": "m1",
                        "MetricStat": {
                            "Metric": {
                                "Namespace": alarm.get("Namespace", ""),
                                "MetricName": alarm.get("MetricName", ""),
                                "Dimensions": alarm.get("Dimensions", []),
                            },
                            "Period": 60,
                            "Stat": alarm.get("Statistic", "Average"),
                        },
                    }
                ],
                StartTime=start,
                EndTime=end,
            )
            values = metric_resp.get("MetricDataResults", [{}])[0].get("Values", [])
            ctx["recent_values"] = values[:10]
        except Exception:
            pass

    return ctx


def _collect_lambda(detail: dict) -> dict:
    """Collect context for a Lambda failure."""
    s = _session()
    region = get_runtime_aws_region()
    lam = s.client("lambda", region_name=region)
    logs = s.client("logs", region_name=region)

    fn_name = detail.get("requestContext", {}).get("functionArn", "").split(":")[-1] or detail.get(
        "functionName", ""
    )
    ctx: dict[str, Any] = {"type": "lambda", "function_name": fn_name, "detail": detail}

    try:
        config = lam.get_function_configuration(FunctionName=fn_name)
        ctx["runtime"] = config.get("Runtime", "")
        ctx["memory"] = config.get("MemorySize")
        ctx["timeout"] = config.get("Timeout")
        ctx["last_modified"] = config.get("LastModified", "")
    except Exception:
        pass

    log_group = f"/aws/lambda/{fn_name}"
    try:
        streams = logs.describe_log_streams(
            logGroupName=log_group, orderBy="LastEventTime", descending=True, limit=1
        )
        if streams.get("logStreams"):
            stream_name = streams["logStreams"][0]["logStreamName"]
            log_events = logs.get_log_events(
                logGroupName=log_group, logStreamName=stream_name, limit=30, startFromHead=False
            )
            ctx["recent_logs"] = [e["message"] for e in log_events.get("events", [])]
    except Exception:
        pass

    return ctx


def _collect_ecs(detail: dict) -> dict:
    """Collect context for an ECS task stopped event."""
    s = _session()
    region = get_runtime_aws_region()
    ecs = s.client("ecs", region_name=region)
    logs = s.client("logs", region_name=region)

    cluster_arn = detail.get("clusterArn", "")
    task_arn = detail.get("taskArn", "")
    ctx: dict[str, Any] = {
        "type": "ecs",
        "cluster": cluster_arn.split("/")[-1] if cluster_arn else "",
        "task_arn": task_arn,
        "stopped_reason": detail.get("stoppedReason", ""),
        "stop_code": detail.get("stopCode", ""),
        "containers": [],
        "detail": detail,
    }

    for container in detail.get("containers", []):
        ctx["containers"].append(
            {
                "name": container.get("name", ""),
                "exit_code": container.get("exitCode"),
                "reason": container.get("reason", ""),
            }
        )

    task_def_arn = detail.get("taskDefinitionArn", "")
    if task_def_arn:
        try:
            td = ecs.describe_task_definition(taskDefinition=task_def_arn)
            containers = td.get("taskDefinition", {}).get("containerDefinitions", [])
            if containers:
                log_config = containers[0].get("logConfiguration", {})
                if log_config.get("logDriver") == "awslogs":
                    opts = log_config.get("options", {})
                    log_group = opts.get("awslogs-group", "")
                    prefix = opts.get("awslogs-stream-prefix", "")
                    task_id = task_arn.split("/")[-1]
                    stream_name = f"{prefix}/{containers[0]['name']}/{task_id}"
                    log_events = logs.get_log_events(
                        logGroupName=log_group,
                        logStreamName=stream_name,
                        limit=30,
                        startFromHead=False,
                    )
                    ctx["recent_logs"] = [e["message"] for e in log_events.get("events", [])]
        except Exception:
            pass

    return ctx


def _collect_ec2(detail: dict) -> dict:
    """Collect context for an EC2 state change."""
    s = _session()
    region = get_runtime_aws_region()
    ec2 = s.client("ec2", region_name=region)

    instance_id = detail.get("instance-id", "")
    ctx: dict[str, Any] = {
        "type": "ec2",
        "instance_id": instance_id,
        "state": detail.get("state", ""),
        "detail": detail,
    }

    try:
        resp = ec2.describe_instances(InstanceIds=[instance_id])
        inst = resp["Reservations"][0]["Instances"][0] if resp.get("Reservations") else {}
        ctx["instance_type"] = inst.get("InstanceType", "")
        ctx["launch_time"] = str(inst.get("LaunchTime", ""))
        ctx["tags"] = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
        status_resp = ec2.describe_instance_status(InstanceIds=[instance_id])
        if status_resp.get("InstanceStatuses"):
            s_info = status_resp["InstanceStatuses"][0]
            ctx["system_status"] = s_info.get("SystemStatus", {}).get("Status", "")
            ctx["instance_status"] = s_info.get("InstanceStatus", {}).get("Status", "")
    except Exception:
        pass

    return ctx


def _collect_rds(detail: dict) -> dict:
    """Collect context for an RDS event."""
    s = _session()
    region = get_runtime_aws_region()
    rds = s.client("rds", region_name=region)

    source_id = detail.get("SourceIdentifier", "")
    ctx: dict[str, Any] = {"type": "rds", "source_id": source_id, "detail": detail}

    try:
        resp = rds.describe_db_instances(DBInstanceIdentifier=source_id)
        if resp.get("DBInstances"):
            db = resp["DBInstances"][0]
            ctx["engine"] = db.get("Engine", "")
            ctx["status"] = db.get("DBInstanceStatus", "")
            ctx["instance_class"] = db.get("DBInstanceClass", "")
            ctx["storage_gb"] = db.get("AllocatedStorage")
            ctx["multi_az"] = db.get("MultiAZ", False)
    except Exception:
        pass

    return ctx


def _collect_codedeploy(detail: dict) -> dict:
    """Collect context for a CodeDeploy failure."""
    return {"type": "codedeploy", "detail": detail}
