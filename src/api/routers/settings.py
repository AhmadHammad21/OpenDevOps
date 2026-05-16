"""Settings endpoint — exposes read-only runtime configuration."""

from __future__ import annotations

from typing import Annotated

import os

from fastapi import APIRouter, Depends

from agent.init_store import get_runtime_aws_region
from api.auth import get_current_user
from config import settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _mask(value: str | None, show_prefix: int = 4) -> str:
    if not value:
        return "(not set)"
    if len(value) <= show_prefix:
        return "••••••••"
    return value[:show_prefix] + "••••••••"


@router.get("")
async def get_settings(
    _user: Annotated[dict | None, Depends(get_current_user)],
) -> dict:
    env = [
        {"key": "LLM_MODEL",           "value": settings.llm_model,                                           "secret": False},
        {"key": "OPENROUTER_API_KEY",  "value": _mask(settings.openrouter_api_key or None),                   "secret": True},
        {"key": "OPENROUTER_BASE_URL", "value": settings.openrouter_base_url or "(not set)",                  "secret": False},
        {"key": "LLM_API_KEY",         "value": _mask(settings.llm_api_key),                                  "secret": True},
        {"key": "LLM_API_BASE",        "value": settings.llm_api_base or "(not set)",                         "secret": False},
        {"key": "AWS_REGION",             "value": settings.aws_region,                                          "secret": False},
        {"key": "AWS_PROFILE",            "value": settings.aws_profile or "(not set)",                          "secret": False},
        {"key": "AWS_ACCESS_KEY_ID",      "value": _mask(os.environ.get("AWS_ACCESS_KEY_ID")),                  "secret": True},
        {"key": "AWS_SECRET_ACCESS_KEY",  "value": _mask(os.environ.get("AWS_SECRET_ACCESS_KEY")),              "secret": True},
        {"key": "CHECKPOINT_BACKEND",  "value": settings.checkpoint_backend,                                  "secret": False},
        {"key": "DATABASE_URL",        "value": _mask(settings.database_url),                                  "secret": True},
        {"key": "SLACK_WEBHOOK_URL",   "value": _mask(settings.slack_webhook_url),                            "secret": True},
        {"key": "JWT_SECRET",          "value": _mask(settings.jwt_secret),                                   "secret": True},
    ]

    agent = [
        {"key": "EFFECTIVE_AWS_REGION",      "label": "Effective AWS region",  "value": get_runtime_aws_region(),                 "hint": "Wizard setting, falling back to AWS_REGION"},
        {"key": "MAX_TOOL_CALLS",               "label": "Max tool calls",         "value": str(settings.max_tool_calls),              "hint": "Hard cap per investigation run"},
        {"key": "INVESTIGATION_TIMEOUT",         "label": "Timeout (s)",            "value": str(settings.investigation_timeout),       "hint": "Max seconds before run is cancelled"},
        {"key": "TOOL_RESPONSE_MAX_CHARS",       "label": "Tool response cap",      "value": str(settings.tool_response_max_chars),     "hint": "Chars before tool output is truncated"},
        {"key": "SUMMARIZATION_ENABLED",         "label": "Auto-summarize",         "value": str(settings.summarization_enabled).lower(),"hint": "Compact sessions that exceed the threshold"},
        {"key": "SUMMARIZATION_THRESHOLD_CHARS", "label": "Summarize threshold",   "value": str(settings.summarization_threshold_chars),"hint": "Total chars in session before compaction fires"},
        {"key": "POLL_INTERVAL_SECONDS",         "label": "Poll interval (s)",      "value": str(settings.poll_interval_seconds),        "hint": "0 = proactive polling disabled"},
        {"key": "EVENT_CONSUMER_ENABLED",        "label": "Event consumer",         "value": str(settings.event_consumer_enabled).lower(), "hint": "EventBridge→SQS incident detection"},
    ]

    return {"env": env, "agent": agent}
