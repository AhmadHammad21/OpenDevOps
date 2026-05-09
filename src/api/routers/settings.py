"""Settings endpoint — exposes read-only runtime configuration."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from api.auth import get_current_user
from config import settings

router = APIRouter(prefix="/settings", tags=["settings"])


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
        {"key": "AWS_REGION",          "value": settings.aws_region,                                          "secret": False},
        {"key": "AWS_PROFILE",         "value": settings.aws_profile or "(not set)",                          "secret": False},
        {"key": "CHECKPOINT_BACKEND",  "value": settings.checkpoint_backend,                                  "secret": False},
        {"key": "DATABASE_URL",        "value": _mask(settings.database_url),                                  "secret": True},
        {"key": "SLACK_WEBHOOK_URL",   "value": _mask(settings.slack_webhook_url),                            "secret": True},
        {"key": "JWT_SECRET",          "value": _mask(settings.jwt_secret),                                   "secret": True},
    ]

    agent = [
        {"key": "MAX_TOOL_CALLS",               "label": "Max tool calls",         "value": str(settings.max_tool_calls),              "hint": "Hard cap per investigation run"},
        {"key": "INVESTIGATION_TIMEOUT",         "label": "Timeout (s)",            "value": str(settings.investigation_timeout),       "hint": "Max seconds before run is cancelled"},
        {"key": "TOOL_RESPONSE_MAX_CHARS",       "label": "Tool response cap",      "value": str(settings.tool_response_max_chars),     "hint": "Chars before tool output is truncated"},
        {"key": "SUMMARIZATION_ENABLED",         "label": "Auto-summarize",         "value": str(settings.summarization_enabled).lower(),"hint": "Compact sessions that exceed the threshold"},
        {"key": "SUMMARIZATION_THRESHOLD_CHARS", "label": "Summarize threshold",   "value": str(settings.summarization_threshold_chars),"hint": "Total chars in session before compaction fires"},
        {"key": "POLL_INTERVAL_MINUTES",         "label": "Poll interval (min)",   "value": str(settings.poll_interval_minutes),       "hint": "0 = proactive polling disabled"},
    ]

    return {"env": env, "agent": agent}
