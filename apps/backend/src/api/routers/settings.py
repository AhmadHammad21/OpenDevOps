"""Settings endpoint — exposes read-only runtime configuration."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from opendevops_core.agent.init_store import get_runtime_aws_region
from opendevops_core.agent.llm import (
    available_providers,
    get_backend_info,
    load_llm_preference,
    save_llm_preference,
)
from pydantic import BaseModel

from api.auth import get_current_user, require_admin
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
    # NOTE: LLM_MODEL intentionally not surfaced here — the picker on the Agent config tab
    # overrides it per-session, so showing the .env default would mislead users about what's
    # actually running. See the LLM card for the active model.
    env = [
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
        {"key": "SLACK_WEBHOOK_URL",    "value": _mask(settings.slack_webhook_url),                           "secret": True},
        {"key": "TELEGRAM_BOT_TOKEN",   "value": _mask(settings.telegram_bot_token),                          "secret": True},
        {"key": "TELEGRAM_CHAT_ID",     "value": settings.telegram_chat_id or "(not set)",                   "secret": False},
        {"key": "JWT_SECRET",           "value": _mask(settings.jwt_secret),                                  "secret": True},
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

    # Use the saved Settings pick (if any) so the LLM display reflects what new sessions
    # will actually use — not the original .env defaults.
    pref = await load_llm_preference()
    return {"env": env, "agent": agent, "llm_backend": get_backend_info(pref=pref)}


# ── LLM picker ──────────────────────────────────────────────────────────────────


class LlmPick(BaseModel):
    source: str | None = None  # detector key (e.g. "claude_code") or empty
    model: str | None = None   # litellm model string, e.g. "anthropic/claude-opus-4-7"


@router.get("/llm")
async def get_llm(
    _user: Annotated[dict | None, Depends(get_current_user)],
) -> dict:
    """Return the available providers (with `configured` flags) plus the saved preference.
    The UI uses this to populate the provider dropdown and pre-select the user's pick."""
    pref = await load_llm_preference()
    return {
        "providers": available_providers(),
        "current": pref or {"source": "", "model": ""},
        "backend": get_backend_info(pref=pref),
    }


@router.put("/llm")
async def put_llm(
    body: LlmPick,
    _admin: Annotated[dict | None, Depends(require_admin)],
) -> dict:
    """Persist a model pick. Validates the choice against `available_providers()` so the
    UI can't save a model whose credentials are missing — surfaces a clear error instead."""
    source = (body.source or "").strip()
    model = (body.model or "").strip()
    if not source and not model:
        raise HTTPException(400, "Pick a provider or a model")

    providers = available_providers()
    by_name = {p["name"]: p for p in providers}

    if source:
        prov = by_name.get(source)
        if prov is None:
            raise HTTPException(400, f"Unknown provider: {source}")
        if not prov["configured"]:
            raise HTTPException(400, f"{prov['label']} is not configured: {prov['note']}")
        if model and source != "claude_code" and model not in prov["models"]:
            # Allow custom model names but warn — actually just accept; LiteLLM resolves it.
            pass
    elif model:
        # Find which provider owns this model and check it's configured.
        owner = next((p for p in providers if model in p["models"]), None)
        if owner and not owner["configured"]:
            raise HTTPException(400, f"{owner['label']} is not configured: {owner['note']}")

    saved = await save_llm_preference(source or None, model or None)
    return {"current": saved}
