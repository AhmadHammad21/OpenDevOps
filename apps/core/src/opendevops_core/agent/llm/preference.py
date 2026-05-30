"""Read/write the user-selected LLM model preference, persisted in the ``app_config`` KV.

The Settings UI lets the user pick a provider + model and save it. That choice flows
back through chat requests via :func:`resolve_for_request`, which is what the chat
router calls to learn what model to use for *new* sessions (existing sessions are
pinned to the model they were created with — see ``sessions.model``).

OSS = one preference for the whole install (org_id is None).
Product = one preference per org (org_id is the caller's org).
"""

from __future__ import annotations

from typing import TypedDict


class LlmPreference(TypedDict, total=False):
    source: str  # detector name (e.g. "claude_code") or "" when picking by model
    model: str   # litellm model string (e.g. "anthropic/claude-opus-4-7")


def _key(org_id: str | None) -> str:
    """KV key under which the preference lives."""
    return f"llm_preference_{org_id}" if org_id else "llm_preference"


async def load_llm_preference(org_id: str | None = None) -> LlmPreference | None:
    """Return the saved preference, or None when nothing is saved (use deployment default).
    Safe to call from any context — errors are swallowed and treated as 'no preference'.
    """
    from opendevops_core.agent.db import db

    try:
        data = await db.get_app_config(_key(org_id))
    except Exception:
        return None
    if not data:
        return None
    return {"source": data.get("source", ""), "model": data.get("model", "")}


async def save_llm_preference(
    source: str | None,
    model: str | None,
    org_id: str | None = None,
) -> LlmPreference:
    """Persist the user's pick to ``app_config``. Either field may be empty when the
    user picks Claude Code (source only) or a specific model (model only).
    """
    from opendevops_core.agent.db import db

    pref: LlmPreference = {"source": source or "", "model": model or ""}
    await db.set_app_config(_key(org_id), dict(pref))
    return pref
