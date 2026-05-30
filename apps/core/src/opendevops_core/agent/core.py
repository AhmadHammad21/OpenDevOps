"""DeepAgents-based investigation agent.

The agent itself is **not** a singleton. We keep a tiny LRU cache keyed by
``(model_name, key_hash)`` so callers can pick a different LLM per request (Settings →
LLM picker; per-org choice in the product) without paying the create_deep_agent
compilation cost on every chat message. First request for a given (model, key) compiles
the agent and caches it; subsequent requests reuse.

The LangGraph checkpointer is set once at startup via :func:`init_agent` and shared
across all cached agent instances — it carries thread (session) state, so the cache key
should not include it.
"""

import asyncio
import hashlib
import json
import re
import uuid
from functools import lru_cache
from typing import Any

from deepagents import create_deep_agent
from langchain_litellm import ChatLiteLLM
from loguru import logger

from opendevops_core.agent.prompts import SYSTEM_PROMPT
from opendevops_core.config import settings
from opendevops_core.models.agent import (
    Confidence,
    Investigation,
    InvestigationResult,
    RootCauseCategory,
)
from opendevops_core.providers import get_active_provider
from opendevops_core.tools._cap import with_cap
from opendevops_core.tools.bash_tool import ALL_BASH_TOOLS
from opendevops_core.tools.final_answer import ALL_FINAL_ANSWER_TOOLS
from opendevops_core.tools.history import ALL_HISTORY_TOOLS
from opendevops_core.tools.skills import ALL_SKILL_TOOLS

# Cloud-agnostic tools available regardless of provider.
SHARED_TOOLS = ALL_HISTORY_TOOLS + ALL_BASH_TOOLS + ALL_SKILL_TOOLS + ALL_FINAL_ANSWER_TOOLS

# Active provider's cloud tools + shared tools. Provider is selected by CLOUD_PROVIDER.
ALL_TOOLS = get_active_provider().tools() + SHARED_TOOLS

# Shared across all cached agent instances; set once during init_agent().
_checkpointer: Any = None

# api_key -> ChatLiteLLM-suitable string. lru_cache stores hashes (so plaintext keys never
# end up in cache.repr), and this map lets us recover the actual key when building the model.
_key_map: dict[str, str | None] = {}


def _key_hash(key: str | None) -> str:
    """Stable, repr-safe identifier for an API key. We register key -> hash both ways so
    the lru_cache can be keyed by hash without exposing the plaintext key in repr/logs."""
    h = hashlib.sha256((key or "").encode()).hexdigest()[:16] if key is not None else "_none_"
    _key_map.setdefault(h, key)
    return h


def get_active_model(model_name: str | None = None) -> str:
    """Return the resolved LLM model string. When called with no arg, returns the
    deployment's default (resolved from env). Chat handlers should pass the per-session
    model that resolve_agent() returned to label cost/usage events accurately."""
    if model_name:
        return model_name
    from opendevops_core.agent.llm import resolve_model_and_key

    m, _ = resolve_model_and_key()
    return m or settings.llm_model


def _run_async(coro: Any) -> Any:
    """Run a coroutine from synchronous CLI code.

    CLI commands are synchronous, so they need a safe bridge into async setup and
    timeout-controlled agent invocation.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("Cannot run synchronous agent call inside an active event loop")


def _build_system_prompt(api_key: str | None) -> Any:
    """Return the system prompt for create_deep_agent — a SystemMessage with the
    Claude Code identity block for subscription OAuth tokens, else a plain string."""
    from opendevops_core.agent.llm import shape_system_content

    content = shape_system_content(SYSTEM_PROMPT, api_key)
    if isinstance(content, list):
        from langchain_core.messages import SystemMessage

        return SystemMessage(content=content)
    return content


@lru_cache(maxsize=8)
def _build_agent(model_name: str, key_hash: str) -> Any:
    """Compile a fresh agent for the given (model, key) tuple. Cached so repeated chat
    requests with the same selection reuse the compiled LangGraph."""
    if _checkpointer is None:
        raise RuntimeError("Agent not initialised — call init_agent() first")
    api_key = _key_map.get(key_hash)
    model = ChatLiteLLM(
        model=model_name,
        api_base=settings.llm_api_base or None,
        api_key=api_key,
    )
    tools = [with_cap(t) for t in ALL_TOOLS] if settings.tool_response_max_chars > 0 else ALL_TOOLS
    logger.info("agent: building compiled graph for model={}", model_name)
    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=_build_system_prompt(api_key),
        checkpointer=_checkpointer,
    )


def resolve_agent(
    override_source: str | None = None,
    override_model: str | None = None,
) -> tuple[Any, str]:
    """Return (agent, model_name) using the override if provided, else the deployment
    default. ``override_source`` accepts a CLI detector name (e.g. ``"claude_code"``) to
    pin to the auto-detected subscription login regardless of CLAUDE_CODE_AUTODETECT.
    """
    from opendevops_core.agent.llm import resolve_model_and_key

    model_name, api_key = resolve_model_and_key(
        override_source=override_source, override_model=override_model
    )
    return _build_agent(model_name, _key_hash(api_key)), model_name


def init_agent(checkpointer: Any) -> None:
    """Set the shared checkpointer and warm the agent cache with the default selection.
    Called once during app startup. The default agent is what serves the CLI and any
    callers that don't pass an explicit model preference."""
    global _checkpointer
    _checkpointer = checkpointer
    _build_agent.cache_clear()
    _key_map.clear()
    # Warm with the default selection so the first chat request is instant.
    resolve_agent()


def get_agent() -> Any:
    """Return the deployment-default compiled agent. Equivalent to ``resolve_agent()[0]``
    for callers (CLI, non-chat entrypoints) that don't have a per-session override."""
    agent, _ = resolve_agent()
    return agent


def ensure_agent_initialized() -> None:
    """Initialize DB + agent lazily for non-API entrypoints (CLI)."""
    if _checkpointer is not None:
        return
    from opendevops_core.agent.db import db

    checkpointer = _run_async(db.init())
    init_agent(checkpointer)


async def ainvoke_with_timeout(
    agent_input: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    """Run agent invocation with a global investigation timeout."""
    return await asyncio.wait_for(
        get_agent().ainvoke(agent_input, config=config),
        timeout=settings.investigation_timeout,
    )


def invoke_with_timeout(agent_input: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Synchronous wrapper for timeout-enforced invocation."""
    return _run_async(ainvoke_with_timeout(agent_input, config))


def _parse_result_json(text: str) -> dict[str, Any] | None:
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    try:
        start = text.rfind("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except json.JSONDecodeError:
        pass
    return None


def _build_result(raw: dict[str, Any]) -> InvestigationResult:
    return InvestigationResult(
        root_cause_category=RootCauseCategory(raw.get("root_cause_category", "UNKNOWN")),
        root_cause_summary=raw.get("root_cause_summary", ""),
        evidence=raw.get("evidence", []),
        mitigation_steps=raw.get("mitigation_steps", []),
        validation_steps=raw.get("validation_steps", []),
        confidence=Confidence(raw.get("confidence", "LOW")),
        services_affected=raw.get("services_affected", []),
        recommended_follow_up=raw.get("recommended_follow_up", ""),
        raw_json=raw,
    )


class InvestigationAgent:
    """Synchronous wrapper for the CLI investigate command."""

    def investigate(self, investigation: Investigation) -> InvestigationResult:
        ensure_agent_initialized()

        user_msg = investigation.description
        if investigation.alarm_name:
            user_msg += f"\nAlarm name: {investigation.alarm_name}"
        if investigation.service:
            user_msg += f"\nService: {investigation.service}"
        if investigation.region:
            user_msg += f"\nRegion: {investigation.region}"

        thread_id = str(uuid.uuid4())
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": settings.max_tool_calls * 3 + 15,
        }

        logger.info("investigation_started description={}", investigation.description)

        result = invoke_with_timeout(
            {"messages": [{"role": "user", "content": user_msg}]},
            config,
        )

        messages = result.get("messages", [])
        last_msg = messages[-1] if messages else None
        content = ""
        if last_msg is not None:
            content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

        logger.info("investigation_complete")

        raw = _parse_result_json(content)
        if raw:
            return _build_result(raw)
        return InvestigationResult(root_cause_summary=content)
