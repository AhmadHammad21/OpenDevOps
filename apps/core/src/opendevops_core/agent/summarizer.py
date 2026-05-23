"""Conversation summarizer — compacts long sessions before context window overflow.

Triggered automatically before each agent call when total message chars exceed
SUMMARIZATION_THRESHOLD_CHARS. Replaces old messages with a structured summary
injected as a HumanMessage, preserving the last SUMMARIZATION_KEEP_CHARS of recent
context intact. The system prompt is never touched — LangGraph handles it separately.

Summarization events are tracked in usage_events with metadata.summarization=True
so the dashboard can report how many sessions and tokens were compacted.
"""

from __future__ import annotations

import time
from typing import Any

from langchain_core.messages import HumanMessage, RemoveMessage
from langchain_litellm import ChatLiteLLM
from loguru import logger

from opendevops_core.config import settings

_SUMMARIZE_SYSTEM = """You are compressing an AWS incident investigation conversation to save context space.

Produce a factual, dense summary covering:
- What is being investigated (original incident or question)
- Key findings from tool calls (metric values, error messages, timestamps, resource names)
- Hypotheses confirmed or ruled out with evidence
- Current investigation state

Be specific — include actual numbers, service names, and timestamps where present.
Keep the summary under 400 words. Use this exact format:

**Investigating:** <one line>
**Key findings:**
- <finding with specifics>
**Ruled out:** <list or "nothing ruled out yet">
**Current state:** <one line>
"""


def _msg_chars(msg: Any) -> int:
    content = getattr(msg, "content", "") or ""
    return len(str(content))


def _total_chars(messages: list) -> int:
    return sum(_msg_chars(m) for m in messages)


def _split_messages(messages: list, keep_chars: int) -> tuple[list, list]:
    """Return (to_summarize, to_keep), always splitting at a HumanMessage boundary.

    Walks from the end accumulating chars until keep_chars is reached, then finds
    the nearest preceding HumanMessage as the split point. This ensures we never
    orphan ToolMessages whose parent AIMessage has been removed.
    """
    if not messages:
        return [], []

    human_indices = [i for i, m in enumerate(messages) if getattr(m, "type", None) == "human"]

    # Need at least 2 human turns — otherwise nothing useful to summarize
    if len(human_indices) < 2:
        return [], messages

    # Walk from end to find the split point
    chars = 0
    split_at = None
    for i in range(len(messages) - 1, -1, -1):
        chars += _msg_chars(messages[i])
        # Only consider HumanMessage boundaries that aren't the very first message
        if chars >= keep_chars and i in set(human_indices) and i > human_indices[0]:
            split_at = i
            break

    if split_at is None:
        return [], messages

    return messages[:split_at], messages[split_at:]


def _format_for_summary(messages: list) -> str:
    """Render messages as readable text for the summarization prompt."""
    lines = []
    for m in messages:
        role = getattr(m, "type", type(m).__name__).upper()
        content = str(getattr(m, "content", "") or "")
        # Truncate very long tool results to keep the summarization prompt reasonable
        if len(content) > 2_000:
            content = content[:2_000] + "... [truncated]"
        lines.append(f"{role}: {content}")
    return "\n\n".join(lines)


async def maybe_summarize(agent: Any, config: dict, session_id: str) -> bool:
    """Check message length and summarize if over threshold. Returns True if ran."""
    if not settings.summarization_enabled or settings.summarization_threshold_chars <= 0:
        return False

    sid = session_id[:8]

    try:
        state = await agent.aget_state(config)
    except Exception as exc:
        logger.warning("[{}] summarizer: could not read state — {}", sid, exc)
        return False

    messages = (state.values or {}).get("messages", [])
    if not messages:
        return False

    total = _total_chars(messages)
    if total <= settings.summarization_threshold_chars:
        return False

    to_summarize, to_keep = _split_messages(messages, settings.summarization_keep_chars)
    if len(to_summarize) < 4:
        return False

    chars_removed = _total_chars(to_summarize)
    logger.info(
        "[{}] summarizer: session={} chars, removing {} msgs ({} chars), keeping {} msgs",
        sid,
        total,
        len(to_summarize),
        chars_removed,
        len(to_keep),
    )

    # ── Summarize old messages via LLM ────────────────────────────────────────
    history_text = _format_for_summary(to_summarize)
    start = time.time()
    try:
        from opendevops_core.agent.llm import resolve_model_and_key, shape_system_content

        model_name, api_key = resolve_model_and_key()
        llm = ChatLiteLLM(
            model=model_name,
            api_base=settings.llm_api_base or None,
            api_key=api_key,
        )
        response = await llm.ainvoke(
            [
                {"role": "system", "content": shape_system_content(_SUMMARIZE_SYSTEM, api_key)},
                {"role": "user", "content": f"Summarize this investigation:\n\n{history_text}"},
            ]
        )
        summary_text = str(response.content)
    except Exception as exc:
        logger.error("[{}] summarizer: LLM call failed — {}", sid, exc)
        return False

    elapsed_ms = int((time.time() - start) * 1000)

    # ── Update LangGraph state ─────────────────────────────────────────────────
    summary_msg = HumanMessage(
        content=(
            "[Context from earlier in this session — summarized to preserve context window]\n\n"
            + summary_text
        )
    )
    removes = [RemoveMessage(id=m.id) for m in to_summarize]

    try:
        await agent.aupdate_state(config, {"messages": removes + [summary_msg]})
    except Exception as exc:
        logger.error("[{}] summarizer: state update failed — {}", sid, exc)
        return False

    logger.info(
        "[{}] summarizer done: -{} chars, summary {} chars, {}ms",
        sid,
        chars_removed,
        len(summary_text),
        elapsed_ms,
    )

    # ── Record in usage_events ─────────────────────────────────────────────────
    from opendevops_core.agent.db import db
    from opendevops_core.agent.turns import calc_cost

    input_tokens = chars_removed // 4
    output_tokens = len(summary_text) // 4
    cost = calc_cost(settings.llm_model, input_tokens, output_tokens)

    try:
        await db.save_usage_event(
            session_id,
            None,
            model=settings.llm_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_ms=elapsed_ms,
            tool_call_count=0,
            metadata={
                "summarization": True,
                "messages_removed": len(to_summarize),
                "chars_removed": chars_removed,
            },
        )
    except Exception as exc:
        logger.warning("[{}] summarizer: could not save usage event — {}", sid, exc)

    return True
