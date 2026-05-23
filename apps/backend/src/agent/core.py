"""DeepAgents-based investigation agent."""

import asyncio
import json
import re
import uuid
from typing import Any

from deepagents import create_deep_agent
from langchain_litellm import ChatLiteLLM
from config import settings
from models.agent import Confidence, Investigation, InvestigationResult, RootCauseCategory
from agent.prompts import SYSTEM_PROMPT
from loguru import logger
from providers import get_active_provider
from tools._cap import with_cap
from tools.bash_tool import ALL_BASH_TOOLS
from tools.final_answer import ALL_FINAL_ANSWER_TOOLS
from tools.history import ALL_HISTORY_TOOLS
from tools.skills import ALL_SKILL_TOOLS

# Cloud-agnostic tools available regardless of provider.
SHARED_TOOLS = ALL_HISTORY_TOOLS + ALL_BASH_TOOLS + ALL_SKILL_TOOLS + ALL_FINAL_ANSWER_TOOLS

# Active provider's cloud tools + shared tools. Provider is selected by CLOUD_PROVIDER.
ALL_TOOLS = get_active_provider().tools() + SHARED_TOOLS

_agent = None
_active_model: str | None = None


def get_active_model() -> str:
    """Return the resolved LLM model string (may differ from settings.llm_model when
    Claude Code auto-detection overrides the default)."""
    return _active_model or settings.llm_model


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
    from agent.llm import shape_system_content
    content = shape_system_content(SYSTEM_PROMPT, api_key)
    if isinstance(content, list):
        from langchain_core.messages import SystemMessage
        return SystemMessage(content=content)
    return content


def init_agent(checkpointer: Any) -> None:
    """Create the agent with the given checkpointer. Called once during app startup."""
    global _agent, _active_model
    from agent.llm import resolve_model_and_key
    model_name, api_key = resolve_model_and_key()
    _active_model = model_name
    model = ChatLiteLLM(
        model=model_name,
        api_base=settings.llm_api_base or None,
        api_key=api_key,
    )
    tools = [with_cap(t) for t in ALL_TOOLS] if settings.tool_response_max_chars > 0 else ALL_TOOLS
    _agent = create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=_build_system_prompt(api_key),
        checkpointer=checkpointer,
    )


def get_agent() -> Any:
    if _agent is None:
        raise RuntimeError("Agent not initialised — call init_agent() first")
    return _agent


def ensure_agent_initialized() -> None:
    """Initialize DB + agent lazily for non-API entrypoints (CLI)."""
    global _agent
    if _agent is not None:
        return
    from agent.db import db

    checkpointer = _run_async(db.init())
    init_agent(checkpointer)


async def ainvoke_with_timeout(agent_input: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
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
