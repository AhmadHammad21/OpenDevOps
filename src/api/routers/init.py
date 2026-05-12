"""Init wizard API — first-run setup for SNS, SQS, and permission checks."""

from __future__ import annotations

import asyncio
import datetime
import json

import boto3
from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from agent.db import db
from agent.init_store import load_init, save_init
from api.auth import hash_password
from config import settings

router = APIRouter(prefix="/api/init", tags=["init"])


class CreateUserBody(BaseModel):
    username: str
    password: str


class SetupBody(BaseModel):
    sns_topic_arn: str = ""
    aws_region: str = "us-east-1"
    sqs_queue_url: str = ""


class SkipBody(BaseModel):
    services: list[str]


@router.get("/status")
async def status():
    data = load_init()
    data["has_user"] = (await db.count_users()) > 0
    return data


@router.post("/create-user")
async def create_user(body: CreateUserBody):
    existing = await db.get_user_by_email(body.username)
    if existing:
        return {"error": "User already exists"}
    user = await db.create_user(
        email=body.username,
        name=body.username,
        password_hash=hash_password(body.password),
        role="admin",
    )
    logger.info("Init: admin user '{}' created", body.username)
    if user:
        return {"id": user.get("id"), "username": body.username}
    return {"error": "Failed to create user"}


@router.post("/setup")
async def setup(body: SetupBody):
    data = load_init()
    data["sns_topic_arn"] = body.sns_topic_arn
    data["aws_region"] = body.aws_region
    if body.sqs_queue_url:
        data["sqs_queue_url"] = body.sqs_queue_url
    save_init(data)
    logger.info("Init setup saved")
    return data


@router.post("/check-permissions")
async def check_permissions_endpoint():
    from agent.permission_checker import check_permissions as _check

    data = load_init()
    results = await asyncio.get_event_loop().run_in_executor(
        None, _check, data.get("sns_topic_arn", "")
    )
    data["permissions"] = {svc: r["passed"] for svc, r in results.items()}
    save_init(data)
    return {"permissions": results}


@router.post("/skip-services")
async def skip_services(body: SkipBody):
    data = load_init()
    data["skipped_services"] = body.services
    save_init(data)
    return {"skipped_services": body.services}


@router.post("/complete")
async def complete():
    data = load_init()

    try:
        from agent.event_infra import setup_event_infra
        result = await asyncio.get_event_loop().run_in_executor(None, setup_event_infra)
        data["sqs_queue_url"] = result["queue_url"]
        data["sqs_queue_arn"] = result["queue_arn"]
        data["eventbridge_rule_arns"] = result["rule_arns"]
        logger.info("Init: event infra created")
    except Exception as e:
        logger.error("Init: event infra setup failed: {}", e)
        return {"initialized": False, "error": str(e)}

    data["initialized"] = True
    save_init(data)
    logger.info("Init complete")

    # Hot-start the event consumer without requiring a server restart
    try:
        from api.app import start_event_consumer
        start_event_consumer()
    except Exception as e:
        logger.warning("Could not hot-start event consumer (will start on next restart): {}", e)

    return {"initialized": True, "error": None}


@router.delete("/infra")
async def teardown_infra():
    """Remove SQS queue and EventBridge rules created by /complete."""
    data = load_init()
    queue_url = data.get("sqs_queue_url") or settings.sqs_queue_url
    rule_arns = data.get("eventbridge_rule_arns") or {}

    if not queue_url:
        raise HTTPException(
            status_code=400,
            detail="No SQS queue URL found — infrastructure may not be set up",
        )

    try:
        from agent.event_infra import teardown_event_infra
        await asyncio.get_event_loop().run_in_executor(
            None, teardown_event_infra, queue_url, rule_arns
        )
    except Exception as e:
        logger.error("Teardown failed: {}", e)
        raise HTTPException(status_code=500, detail=str(e))

    data["initialized"] = False
    data["sqs_queue_url"] = ""
    data["sqs_queue_arn"] = ""
    data["eventbridge_rule_arns"] = {}
    save_init(data)
    logger.info("Init: event infra torn down")
    return {"torn_down": True}


class TestEventBody(BaseModel):
    service: str = "lambda"


@router.post("/test-event")
async def send_test_event(body: TestEventBody):
    """Put a synthetic event into the SQS queue to verify the pipeline end-to-end."""
    data = load_init()
    queue_url = data.get("sqs_queue_url") or settings.sqs_queue_url
    if not queue_url:
        raise HTTPException(
            status_code=400,
            detail=(
                "Event monitoring not configured — set up the SQS queue in"
                " Settings → AWS Configuration first"
            ),
        )

    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    event: dict = {
        "source": "aws.cloudwatch",
        "detail-type": "CloudWatch Alarm State Change",
        "time": now,
        "detail": {
            "alarmName": "opendevops-test-lambda-errors",
            "state": {
                "value": "ALARM",
                "reason": (
                    "Threshold Crossed: 5 datapoints were greater than or equal to the"
                    " threshold (1.0). The most recent datapoints: [5.0, 3.0, 2.0, 1.0, 1.0]."
                ),
            },
            "configuration": {
                "metrics": [{
                    "metricStat": {
                        "metric": {
                            "namespace": "AWS/Lambda",
                            "name": "Errors",
                            "dimensions": {},
                        },
                        "period": 300,
                        "stat": "Sum",
                    }
                }]
            },
        },
    }

    try:
        s = (
            boto3.Session(profile_name=settings.aws_profile)
            if settings.aws_profile
            else boto3.Session()
        )
        sqs = s.client("sqs", region_name=settings.aws_region)
        resp = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(event)),
        )
        message_id = resp.get("MessageId", "")
        logger.info("Test event sent to SQS: message_id={}", message_id)
        return {"message_id": message_id, "queue_url": queue_url}
    except Exception as e:
        logger.error("Failed to send test event: {}", e)
        raise HTTPException(status_code=500, detail=str(e))
