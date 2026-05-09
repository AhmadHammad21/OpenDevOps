"""Init wizard API — first-run setup for SNS, SQS, and permission checks."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel

from agent.db import db
from agent.init_store import load_init, save_init
from api.auth import hash_password

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
