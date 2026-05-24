"""Shared turn-persistence helpers — used by the chat endpoint, MCP server, and poller."""

from __future__ import annotations

from typing import Any

from loguru import logger

from opendevops_core.agent.db import db
from opendevops_core.agent.init_store import get_runtime_aws_region
from opendevops_core.config import settings

# Fallback pricing ($/M tokens) for models absent from LiteLLM's database.
_FALLBACK_PRICING: dict[str, dict[str, float]] = {
    "openrouter/google/gemma-4-26b-a4b-it": {"input": 0.07, "output": 0.35},
    "openrouter/google/gemma-2-9b-it": {"input": 0.06, "output": 0.06},
    "openrouter/meta-llama/llama-3.1-8b-instruct": {"input": 0.055, "output": 0.055},
    "openrouter/mistralai/mistral-7b-instruct": {"input": 0.055, "output": 0.055},
}


def calc_cost(model: str, input_tok: int, output_tok: int) -> float | None:
    try:
        import litellm

        info = litellm.model_cost.get(model)
        if info:
            return input_tok * info.get("input_cost_per_token", 0) + output_tok * info.get(
                "output_cost_per_token", 0
            )
        fallback = _FALLBACK_PRICING.get(model)
        if fallback:
            return (input_tok / 1e6) * fallback["input"] + (output_tok / 1e6) * fallback["output"]
        return None
    except Exception:
        return None


async def save_turn(
    session_id: str,
    user_message: str,
    assistant_text: str,
    tool_calls_log: list[dict[str, Any]],
    usage: dict[str, Any],
    source: str = "chat",
    org_id: str | None = None,
    user_id: str | None = None,
) -> None:
    """Persist a completed turn to Postgres. Errors are logged, never raised."""
    try:
        title = user_message[:80] if user_message else None
        await db.upsert_session(
            session_id,
            usage.get("model", ""),
            get_runtime_aws_region(),
            title,
            source,
            org_id=org_id,
            user_id=user_id,
        )

        await db.save_message(session_id, "user", user_message)
        asst_msg_id = await db.save_message(
            session_id,
            "assistant",
            assistant_text,
            metadata={"model": usage.get("model"), "latency_ms": usage.get("latency_ms")},
        )

        for tc in tool_calls_log:
            await db.save_tool_call(
                session_id,
                asst_msg_id,
                tc["tool"],
                tc["args"],
                tc["result"],
            )

        cost = calc_cost(
            usage.get("model", ""),
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0),
        )
        await db.save_usage_event(
            session_id,
            asst_msg_id,
            model=usage.get("model", ""),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cost_usd=cost,
            latency_ms=usage.get("latency_ms", 0),
            tool_call_count=len(tool_calls_log),
        )
    except Exception as e:
        logger.error("[{}]  DB save failed: {}", session_id[:8], e)


async def notify_slack(session_id: str, tool_calls_log: list[dict[str, Any]]) -> bool:
    """Post to Slack if submit_investigation was called and a webhook is configured.

    Returns True if the message was sent successfully, False otherwise.
    """
    if not settings.slack_webhook_url:
        return False
    for tc in tool_calls_log:
        if tc.get("tool") == "submit_investigation":
            from opendevops_core.integrations.slack_webhook import post_investigation

            return await post_investigation(settings.slack_webhook_url, tc["args"], session_id)
    return False
