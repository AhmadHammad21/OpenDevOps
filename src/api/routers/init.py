"""Init wizard API — first-run setup for SNS, SQS, and permission checks."""

from __future__ import annotations

import asyncio
import datetime
import json
from typing import Annotated

import boto3
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, EmailStr, Field

from agent.db import db
from agent.init_store import (
    get_runtime_aws_region,
    get_runtime_sqs_queue_url,
    load_init_async,
    save_init_async,
)
from api.auth import hash_password, require_admin
from config import settings

router = APIRouter(prefix="/api/init", tags=["init"])


class CreateUserBody(BaseModel):
    username: EmailStr
    password: str = Field(min_length=8)


class SetupBody(BaseModel):
    sns_topic_arn: str = ""
    aws_region: str = "us-east-1"
    sqs_queue_url: str = ""
    org_name: str = ""


class SkipBody(BaseModel):
    services: list[str]


@router.post("/reset")
async def reset_init_state(
    _: Annotated[dict | None, Depends(require_admin)],
):
    """Clear persisted init/setup state. Useful for re-running the wizard without touching AWS."""
    from agent.init_store import reset_init_async

    await reset_init_async()
    return {"reset": True}


@router.get("/status")
async def status():
    data = await load_init_async()
    has_user = (await db.count_users()) > 0
    data["has_user"] = has_user
    data["auth_enabled"] = bool(settings.jwt_secret)
    data["needs_setup"] = not bool(data.get("setup_complete"))
    data["initialized"] = bool(data.get("setup_complete"))
    data["event_infra_enabled"] = bool(get_runtime_sqs_queue_url()) and bool(
        settings.sqs_queue_url or data.get("event_infra_enabled")
    )
    return data


@router.post("/create-user")
async def create_user(body: CreateUserBody):
    username = str(body.username)
    user_count = await db.count_users()
    if user_count > 0:
        raise HTTPException(status_code=409, detail="Initial admin account already exists")
    existing = await db.get_user_by_email(username)
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")

    user = await db.create_user(
        email=username,
        name=username,
        password_hash=hash_password(body.password),
        role="admin",
    )
    logger.info("Init: admin user '{}' created", username)
    if user:
        return {"id": user.get("id"), "username": username}
    raise HTTPException(status_code=500, detail="Failed to create user")


@router.post("/setup")
async def setup(
    body: SetupBody,
    _: Annotated[dict | None, Depends(require_admin)],
):
    import re

    data = await load_init_async()
    data["sns_topic_arn"] = body.sns_topic_arn.strip()
    data["aws_region"] = body.aws_region.strip() or settings.aws_region
    data["sqs_queue_url"] = body.sqs_queue_url.strip()
    data["event_infra_enabled"] = bool(data["sqs_queue_url"])
    data["event_infra_managed"] = False
    if data["sqs_queue_url"]:
        data["sqs_queue_arn"] = ""
        data["eventbridge_rule_arns"] = {}

    # Create org if name provided and none exists yet
    if body.org_name.strip():
        existing_org = await db.get_first_org()
        if not existing_org:
            slug = re.sub(r"[^a-z0-9]+", "-", body.org_name.strip().lower()).strip("-") or "org"
            org = await db.create_org(body.org_name.strip(), slug)
            if org:
                logger.info("Init: organization '{}' created", body.org_name)
                await db.assign_org_to_users_without_org(org["id"])

    data = await save_init_async(data)
    logger.info("Init setup saved")
    return data


@router.post("/check-permissions")
async def check_permissions_endpoint(
    _: Annotated[dict | None, Depends(require_admin)],
):
    from agent.permission_checker import check_permissions as _check

    data = await load_init_async()
    results = await asyncio.get_event_loop().run_in_executor(
        None, _check, data.get("sns_topic_arn", ""), data.get("aws_region")
    )
    data["permissions"] = {svc: r["passed"] for svc, r in results.items()}
    await save_init_async(data)
    return {"permissions": results}


@router.post("/skip-services")
async def skip_services(
    body: SkipBody,
    _: Annotated[dict | None, Depends(require_admin)],
):
    data = await load_init_async()
    data["skipped_services"] = body.services
    data["setup_complete"] = True
    data["initialized"] = True
    await save_init_async(data)
    return {"skipped_services": body.services}


@router.post("/complete")
async def complete(
    _: Annotated[dict | None, Depends(require_admin)],
):
    data = await load_init_async()
    region = data.get("aws_region") or settings.aws_region

    try:
        from agent.event_infra import setup_event_infra

        result = await asyncio.get_event_loop().run_in_executor(None, setup_event_infra, region)
        data["sqs_queue_url"] = result["queue_url"]
        data["sqs_queue_arn"] = result["queue_arn"]
        data["eventbridge_rule_arns"] = result["rule_arns"]
        data["event_infra_enabled"] = True
        data["event_infra_managed"] = True
        logger.info("Init: event infra created")
    except Exception as e:
        logger.error("Init: event infra setup failed: {}", e)
        raise HTTPException(status_code=500, detail=str(e))

    data["setup_complete"] = True
    data["initialized"] = True
    await save_init_async(data)
    logger.info("Init complete")

    # Hot-start the event consumer without requiring a server restart
    try:
        from api.app import start_event_consumer, stop_event_consumer

        await stop_event_consumer()
        start_event_consumer()
    except Exception as e:
        logger.warning("Could not hot-start event consumer (will start on next restart): {}", e)

    return {"initialized": True, "event_infra_enabled": True, "error": None}


@router.delete("/infra")
async def teardown_infra(
    _: Annotated[dict | None, Depends(require_admin)],
):
    """Remove SQS queue and EventBridge rules created by /complete."""
    data = await load_init_async()
    queue_url = data.get("sqs_queue_url") or ""
    rule_arns = data.get("eventbridge_rule_arns") or {}
    region = data.get("aws_region") or settings.aws_region
    managed = bool(data.get("event_infra_managed"))

    if settings.sqs_queue_url and not managed:
        raise HTTPException(
            status_code=400,
            detail=(
                "Event monitoring is configured by SQS_QUEUE_URL. Remove that environment "
                "variable and restart to disable it from the app."
            ),
        )

    if queue_url and not managed:
        data["event_infra_enabled"] = False
        data["sqs_queue_url"] = ""
        await save_init_async(data)
        try:
            from api.app import stop_event_consumer

            await stop_event_consumer()
        except Exception as e:
            logger.warning("Could not stop event consumer after disabling external queue: {}", e)
        return {
            "torn_down": True,
            "warnings": ["External SQS queue was disconnected but not deleted"],
        }

    if not queue_url and not rule_arns:
        data["event_infra_enabled"] = False
        data["event_infra_managed"] = False
        await save_init_async(data)
        return {"torn_down": True, "warnings": ["No event infrastructure was configured"]}

    try:
        from agent.event_infra import teardown_event_infra

        result = await asyncio.get_event_loop().run_in_executor(
            None, teardown_event_infra, queue_url, rule_arns, region
        )
    except Exception as e:
        logger.error("Teardown failed: {}", e)
        raise HTTPException(status_code=500, detail=str(e))

    if result.get("errors"):
        raise HTTPException(status_code=500, detail=result)

    data["event_infra_enabled"] = False
    data["sqs_queue_url"] = ""
    data["sqs_queue_arn"] = ""
    data["eventbridge_rule_arns"] = {}
    data["event_infra_managed"] = False
    await save_init_async(data)

    try:
        from api.app import stop_event_consumer

        await stop_event_consumer()
    except Exception as e:
        logger.warning("Could not stop event consumer after teardown: {}", e)

    logger.info("Init: event infra torn down")
    return {"torn_down": True, "warnings": result.get("warnings", [])}


class TestEventBody(BaseModel):
    service: str = "lambda"


@router.post("/test-event")
async def send_test_event(
    body: TestEventBody,
    _: Annotated[dict | None, Depends(require_admin)],
):
    """Put a synthetic event into the SQS queue to verify the pipeline end-to-end."""
    if body.service != "lambda":
        raise HTTPException(status_code=400, detail="Only lambda test events are supported")

    await load_init_async()
    queue_url = get_runtime_sqs_queue_url()
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
        "_opendevops_test": True,
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
                "metrics": [
                    {
                        "metricStat": {
                            "metric": {
                                "namespace": "AWS/Lambda",
                                "name": "Errors",
                                "dimensions": {},
                            },
                            "period": 300,
                            "stat": "Sum",
                        }
                    }
                ]
            },
        },
    }

    try:
        s = (
            boto3.Session(profile_name=settings.aws_profile)
            if settings.aws_profile
            else boto3.Session()
        )
        sqs = s.client("sqs", region_name=get_runtime_aws_region())
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
