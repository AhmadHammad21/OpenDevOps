"""Shared investigation runner — used by both the poller and event consumer."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from loguru import logger

from opendevops_core.config import settings


async def run_investigation(
    prompt: str, session_id: str
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Run a full agent investigation. Returns (result, tool_calls_log).

    Both the poller and the event consumer use this. result is None only when the
    LLM never called submit_investigation (e.g. MAX_TOOL_CALLS hit without finishing).
    On agent exception, result is returned with _status="failed" so callers can still
    persist a record and send notifications.
    """
    from opendevops_core.agent.core import get_agent
    from opendevops_core.agent.turns import save_turn

    def _f(obj: Any, key: str, default: Any = None) -> Any:
        return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)

    config = {
        "configurable": {"thread_id": session_id},
        "recursion_limit": settings.max_tool_calls * 3 + 15,
    }

    tc_accum: dict[int, dict[str, Any]] = {}
    pending_calls: dict[str, dict[str, Any]] = {}
    tool_calls_log: list[dict[str, Any]] = []
    investigation_result: dict[str, Any] | None = None
    response_text = ""
    usage_meta: Any = None

    try:
        async with asyncio.timeout(settings.investigation_timeout):
            async for chunk, _meta in get_agent().astream(
                {"messages": [{"role": "user", "content": prompt}]},
                config=config,
                stream_mode="messages",
            ):
                um = getattr(chunk, "usage_metadata", None)
                if um:
                    usage_meta = um

                for tcc in getattr(chunk, "tool_call_chunks", []) or []:
                    idx = _f(tcc, "index", 0)
                    if idx not in tc_accum:
                        tc_accum[idx] = {"id": "", "name": "", "args_str": ""}
                    if tc_id := _f(tcc, "id"):
                        tc_accum[idx]["id"] = tc_id
                    if name := (_f(tcc, "name") or ""):
                        tc_accum[idx]["name"] += name
                    if args := (_f(tcc, "args") or ""):
                        tc_accum[idx]["args_str"] += args

                for tc in getattr(chunk, "tool_calls", []) or []:
                    tc_id = _f(tc, "id") or ""
                    name = _f(tc, "name") or ""
                    args = _f(tc, "args") or {}
                    if tc_id and name:
                        pending_calls[tc_id] = {
                            "tool": name,
                            "args": args if isinstance(args, dict) else {},
                        }

                content = getattr(chunk, "content", "")
                tc_id = getattr(chunk, "tool_call_id", None)

                if content and isinstance(content, str) and not tc_id:
                    response_text += content

                if tc_id:
                    for entry in tc_accum.values():
                        if eid := entry["id"]:
                            try:
                                eargs: Any = (
                                    json.loads(entry["args_str"]) if entry["args_str"] else {}
                                )
                            except json.JSONDecodeError:
                                eargs = {}
                            pending_calls[eid] = {"tool": entry["name"], "args": eargs}
                    tc_accum.clear()

                    call_info = pending_calls.pop(
                        tc_id,
                        {"tool": getattr(chunk, "name", None) or "unknown", "args": {}},
                    )
                    try:
                        result = json.loads(content)
                    except (json.JSONDecodeError, TypeError):
                        result = {"raw": str(content)[:500]}

                    tool_calls_log.append(
                        {
                            "tool": call_info["tool"],
                            "args": call_info["args"],
                            "result": result,
                        }
                    )
                    if call_info["tool"] == "submit_investigation":
                        investigation_result = call_info["args"]

    except Exception as e:
        logger.error("Investigation failed: {}", e)
        investigation_result = {
            "_status": "failed",
            "root_cause_summary": f"Investigation failed: {e}",
            "confidence": "LOW",
            "mitigation_steps": [
                "Re-investigate manually via the chat — use a higher MAX_TOOL_CALLS if needed.",
            ],
        }

    # Agent completed without calling submit_investigation (e.g. hit recursion limit or
    # the model doesn't support tool use reliably). Synthesize a failed result so callers
    # always get a non-None value and can still persist + notify.
    if investigation_result is None:
        summary = response_text.strip() or "Agent completed without producing a structured result."
        logger.warning(
            "Investigation ended without submit_investigation — synthesising failed result"
        )
        investigation_result = {
            "_status": "failed",
            "root_cause_summary": summary[:500],
            "confidence": "LOW",
            "mitigation_steps": [
                "Re-investigate manually via the chat.",
                "Consider switching to a model with stronger tool-use support.",
            ],
        }

    if (
        investigation_result
        and investigation_result.get("root_cause_summary")
        and "_status" not in investigation_result
    ):
        steps = investigation_result.get("mitigation_steps", [])
        steps_text = "\n".join(f"- {s}" for s in steps) if steps else "_No steps provided._"
        confidence = investigation_result.get("confidence", "MEDIUM")
        assistant_text = (
            f"**Root Cause ({confidence} confidence):** "
            f"{investigation_result['root_cause_summary']}\n\n"
            f"**Mitigation Steps:**\n{steps_text}"
        )
    elif response_text.strip():
        assistant_text = response_text.strip()
    else:
        assistant_text = "Investigation completed. See tool calls for details."

    await save_turn(
        session_id=session_id,
        user_message=prompt,
        assistant_text=assistant_text,
        tool_calls_log=tool_calls_log,
        usage={
            "model": settings.llm_model,
            "input_tokens": _f(usage_meta, "input_tokens", 0) or 0,
            "output_tokens": _f(usage_meta, "output_tokens", 0) or 0,
            "latency_ms": 0,
        },
        source="event",
    )

    return investigation_result, tool_calls_log
