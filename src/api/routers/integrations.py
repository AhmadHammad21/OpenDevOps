"""Integrations router — manage third-party integration actions (e.g. Slack test)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user
from config import settings

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.post("/slack/test")
async def test_slack(
    _user: Annotated[dict | None, Depends(get_current_user)],
) -> dict:
    """Send a test Slack message to verify the webhook is working."""
    if not settings.slack_webhook_url:
        raise HTTPException(status_code=400, detail="SLACK_WEBHOOK_URL is not configured")

    from integrations.slack_webhook import post_investigation

    test_result = {
        "root_cause_category": "SYSTEM_CHANGE",
        "root_cause_summary": (
            "This is a test message from OpenDevOps Agent "
            "to verify your Slack integration is working correctly."
        ),
        "confidence": "HIGH",
        "evidence": ["Test triggered from Settings → Integrations"],
        "mitigation_steps": ["No action needed — this is a test"],
        "services_affected": ["OpenDevOps Agent"],
    }
    session_id = str(uuid.uuid4())
    await post_investigation(
        webhook_url=settings.slack_webhook_url,
        result=test_result,
        session_id=session_id,
        is_test=True,
    )
    return {"ok": True}
