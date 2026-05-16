"""Event infrastructure setup — creates SQS queue + EventBridge rules during init."""

from __future__ import annotations

import json

import boto3
from botocore.exceptions import ClientError
from loguru import logger

from config import settings

QUEUE_NAME = "opendevops-agent-events"

# EventBridge rule definitions: name → event pattern
RULES: dict[str, dict] = {
    "opendevops-alarm-state": {
        "source": ["aws.cloudwatch"],
        "detail-type": ["CloudWatch Alarm State Change"],
        "detail": {"state": {"value": ["ALARM"]}},
    },
    "opendevops-lambda-failure": {
        "source": ["aws.lambda"],
        "detail-type": ["Lambda Function Invocation Result - Failure"],
    },
    "opendevops-lambda-throttle": {
        "source": ["aws.lambda"],
        "detail-type": [
            "Lambda Function Invocation Result - Failure",
            "AWS API Call via CloudTrail",
        ],
        "detail": {"errorCode": ["TooManyRequestsException", "Throttling"]},
    },
    "opendevops-ecs-task-stopped": {
        "source": ["aws.ecs"],
        "detail-type": ["ECS Task State Change"],
        "detail": {
            "lastStatus": ["STOPPED"],
            "stopCode": [
                "TaskFailedToStart",
                "EssentialContainerExited",
                "ServiceSchedulerInitiated",
            ],
            "containers": {"exitCode": [{"anything-but": 0}]},
        },
    },
    "opendevops-ec2-state": {
        "source": ["aws.ec2"],
        "detail-type": ["EC2 Instance State-change Notification"],
        "detail": {"state": ["terminated"]},
    },
    "opendevops-rds-events": {
        "source": ["aws.rds"],
        "detail-type": ["RDS DB Instance Event"],
        "detail": {
            "EventCategories": ["failure", "failover", "recovery", "notification"],
        },
    },
    "opendevops-health": {
        "source": ["aws.health"],
        "detail-type": ["AWS Health Event"],
    },
    "opendevops-codedeploy-failure": {
        "source": ["aws.codedeploy"],
        "detail-type": ["CodeDeploy Deployment State-change Notification"],
        "detail": {"state": ["FAILURE"]},
    },
    "opendevops-guardduty": {
        "source": ["aws.guardduty"],
        "detail-type": ["GuardDuty Finding"],
    },
}


def _session() -> boto3.Session:
    return (
        boto3.Session(profile_name=settings.aws_profile)
        if settings.aws_profile
        else boto3.Session()
    )


ALARM_NAME = "opendevops-lambda-errors-aggregate"


def _missing_resource(exc: Exception) -> bool:
    if not isinstance(exc, ClientError):
        return False
    code = exc.response.get("Error", {}).get("Code", "")
    return code in {
        "ResourceNotFoundException",
        "AWS.SimpleQueueService.NonExistentQueue",
        "QueueDoesNotExist",
    }


def setup_event_infra(region: str | None = None) -> dict:
    """Create SQS queue, EventBridge rules, and aggregate Lambda alarm.

    Returns {queue_url, queue_arn, rule_arns}.
    """
    s = _session()
    region = region or settings.aws_region
    sqs = s.client("sqs", region_name=region)
    events = s.client("events", region_name=region)
    cw = s.client("cloudwatch", region_name=region)
    sts = s.client("sts", region_name=region)

    account_id = sts.get_caller_identity()["Account"]
    queue_url = ""
    rule_arns: dict[str, str] = {}

    try:
        resp = sqs.create_queue(
            QueueName=QUEUE_NAME,
            Attributes={
                "MessageRetentionPeriod": "86400",
                "VisibilityTimeout": "120",
                "ReceiveMessageWaitTimeSeconds": "20",
            },
        )
        queue_url = resp["QueueUrl"]
        queue_attrs = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])
        queue_arn = queue_attrs["Attributes"]["QueueArn"]

        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowEventBridge",
                    "Effect": "Allow",
                    "Principal": {"Service": "events.amazonaws.com"},
                    "Action": "sqs:SendMessage",
                    "Resource": queue_arn,
                    "Condition": {
                        "ArnLike": {
                            "aws:SourceArn": (
                                f"arn:aws:events:{region}:{account_id}:rule/opendevops-*"
                            )
                        }
                    },
                }
            ],
        }
        sqs.set_queue_attributes(QueueUrl=queue_url, Attributes={"Policy": json.dumps(policy)})

        for rule_name, pattern in RULES.items():
            resp = events.put_rule(
                Name=rule_name,
                EventPattern=json.dumps(pattern),
                State="ENABLED",
                Description=f"OpenDevOps Agent — {rule_name}",
            )
            rule_arns[rule_name] = resp["RuleArn"]
            events.put_targets(
                Rule=rule_name,
                Targets=[{"Id": "opendevops-sqs", "Arn": queue_arn}],
            )

        # Aggregate CloudWatch alarm — fires when ANY Lambda in the account errors.
        # No dimensions = account-wide. EventBridge alarm-state rule routes it to SQS.
        cw.put_metric_alarm(
            AlarmName=ALARM_NAME,
            AlarmDescription="OpenDevOps Agent — triggers investigation on any Lambda error",
            Namespace="AWS/Lambda",
            MetricName="Errors",
            Statistic="Sum",
            Period=60,
            EvaluationPeriods=1,
            Threshold=1,
            ComparisonOperator="GreaterThanOrEqualToThreshold",
            TreatMissingData="notBreaching",
        )
    except Exception:
        if queue_url or rule_arns:
            teardown_event_infra(queue_url, rule_arns, region)
        raise

    logger.info(
        "Event infra created: queue={} rules={} alarm={}", queue_url, len(rule_arns), ALARM_NAME
    )
    return {"queue_url": queue_url, "queue_arn": queue_arn, "rule_arns": rule_arns}


def teardown_event_infra(
    queue_url: str | None,
    rule_arns: dict[str, str] | None,
    region: str | None = None,
) -> dict:
    """Remove EventBridge rules, aggregate CloudWatch alarm, and SQS queue."""
    s = _session()
    region = region or settings.aws_region
    sqs = s.client("sqs", region_name=region)
    events = s.client("events", region_name=region)
    cw = s.client("cloudwatch", region_name=region)
    warnings: list[str] = []
    errors: list[str] = []

    rules_to_delete = list((rule_arns or {}).keys()) or list(RULES.keys())
    for rule_name in rules_to_delete:
        try:
            resp = events.remove_targets(Rule=rule_name, Ids=["opendevops-sqs"])
            if resp.get("FailedEntryCount"):
                errors.append(f"Failed to remove target for rule {rule_name}: {resp}")
            events.delete_rule(Name=rule_name)
        except Exception as e:
            message = f"Failed to delete rule {rule_name}: {e}"
            logger.warning(message)
            if _missing_resource(e):
                warnings.append(message)
            else:
                errors.append(message)

    try:
        cw.delete_alarms(AlarmNames=[ALARM_NAME])
    except Exception as e:
        message = f"Failed to delete alarm {ALARM_NAME}: {e}"
        logger.warning(message)
        if _missing_resource(e):
            warnings.append(message)
        else:
            errors.append(message)

    if queue_url:
        try:
            sqs.delete_queue(QueueUrl=queue_url)
        except Exception as e:
            message = f"Failed to delete queue: {e}"
            logger.warning(message)
            if _missing_resource(e):
                warnings.append(message)
            else:
                errors.append(message)
    else:
        warnings.append("No queue URL was configured")

    logger.info("Event infra torn down")
    return {"warnings": warnings, "errors": errors}
