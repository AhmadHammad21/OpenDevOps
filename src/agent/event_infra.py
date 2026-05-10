"""Event infrastructure setup — creates SQS queue + EventBridge rules during init."""

from __future__ import annotations

import json

import boto3
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
        "detail-type": ["Lambda Function Invocation Result - Failure", "AWS API Call via CloudTrail"],
        "detail": {"errorCode": ["TooManyRequestsException", "Throttling"]},
    },
    "opendevops-ecs-task-stopped": {
        "source": ["aws.ecs"],
        "detail-type": ["ECS Task State Change"],
        "detail": {
            "lastStatus": ["STOPPED"],
            "stopCode": ["TaskFailedToStart", "EssentialContainerExited", "ServiceSchedulerInitiated"],
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
    return boto3.Session(profile_name=settings.aws_profile) if settings.aws_profile else boto3.Session()


def setup_event_infra() -> dict:
    """Create SQS queue and EventBridge rules. Returns {queue_url, queue_arn, rule_arns}."""
    s = _session()
    region = settings.aws_region
    sqs = s.client("sqs", region_name=region)
    events = s.client("events", region_name=region)
    sts = s.client("sts", region_name=region)

    account_id = sts.get_caller_identity()["Account"]

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
        "Statement": [{
            "Sid": "AllowEventBridge",
            "Effect": "Allow",
            "Principal": {"Service": "events.amazonaws.com"},
            "Action": "sqs:SendMessage",
            "Resource": queue_arn,
            "Condition": {"ArnLike": {"aws:SourceArn": f"arn:aws:events:{region}:{account_id}:rule/opendevops-*"}},
        }],
    }
    sqs.set_queue_attributes(QueueUrl=queue_url, Attributes={"Policy": json.dumps(policy)})

    rule_arns: dict[str, str] = {}
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

    logger.info("Event infra created: queue={} rules={}", queue_url, len(rule_arns))
    return {"queue_url": queue_url, "queue_arn": queue_arn, "rule_arns": rule_arns}


def teardown_event_infra(queue_url: str, rule_arns: dict[str, str]) -> None:
    """Remove EventBridge rules and SQS queue."""
    s = _session()
    region = settings.aws_region
    sqs = s.client("sqs", region_name=region)
    events = s.client("events", region_name=region)

    for rule_name in rule_arns:
        try:
            events.remove_targets(Rule=rule_name, Ids=["opendevops-sqs"])
            events.delete_rule(Name=rule_name)
        except Exception as e:
            logger.warning("Failed to delete rule {}: {}", rule_name, e)

    try:
        sqs.delete_queue(QueueUrl=queue_url)
    except Exception as e:
        logger.warning("Failed to delete queue: {}", e)

    logger.info("Event infra torn down")
