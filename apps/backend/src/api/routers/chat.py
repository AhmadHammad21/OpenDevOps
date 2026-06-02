"""Chat endpoint — SSE streaming with the LangGraph agent."""

from __future__ import annotations

import asyncio
import json
import random
import re
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from opendevops_core.agent.core import resolve_agent
from opendevops_core.agent.db import db
from opendevops_core.agent.llm import load_llm_preference
from opendevops_core.agent.summarizer import maybe_summarize
from opendevops_core.agent.turns import calc_cost, notify_slack, save_turn
from opendevops_core.models.chat import ChatRequest

from api.streaming_labels import STREAMING_LABELS
from config import settings

router = APIRouter(tags=["chat"])

# Maps session_id → Event; set by DELETE /chat/{session_id} to stop an active stream.
_cancel_events: dict[str, asyncio.Event] = {}


def _field(obj: Any, key: str, default: Any = None) -> Any:
    """Read a field from either a dict or a typed object (e.g. ToolCallChunk)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_SEP = "─" * 60

# Strip DeepAgents channel markers and lone artifact words the model leaks into output.
_CHANNEL_RE = re.compile(
    r"<channel\|[^>]*>"           # <channel|thought>
    r"|<channel\|>[a-zA-Z_]*\s*"  # <channel|>thought
    r"|^thought\s*$",             # bare "thought" on its own line
    re.IGNORECASE | re.MULTILINE,
)



def _pick_label(tool_name: str) -> str:
    labels = STREAMING_LABELS.get(tool_name) or STREAMING_LABELS["default"]
    return random.choice(labels)


def _sid(session_id: str) -> str:
    return session_id[:8]


def _clean(text: str) -> str:
    return _CHANNEL_RE.sub("", text)


def _extract_text(content: Any) -> str:
    """Pull the user-visible text out of a chunk's ``content``, regardless of shape.

    Reasoning / hybrid models (gpt-oss, OpenAI o1-family, some Anthropic configs,
    Gemini Thinking) return ``content`` as a list of typed blocks:

        [{'type': 'thinking', 'thinking': '...internal reasoning...'},
         {'type': 'text',     'text':     'the actual answer'}]

    Only the ``text`` blocks go to the UI; ``thinking`` blocks are billed but
    not shown (they're shown via the tool-call inspector / reasoning UI if we
    ever surface them). Plain-string content (older models, Sonnet, GPT-4o)
    flows through unchanged.
    """
    if not content:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                txt = block.get("text") or ""
                if isinstance(txt, str):
                    parts.append(txt)
        return "".join(parts)
    return ""




async def _stream_chat(session_id: str, user_message: str):
    """Stream SSE events to the frontend."""
    # Pin existing sessions to their original model so the user's "switch model" action
    # in Settings only affects NEW chats. For new sessions, use the saved preference.
    pinned_model = await db.get_session_model(session_id)
    if pinned_model:
        agent, active_model = resolve_agent(override_model=pinned_model)
    else:
        pref = await load_llm_preference()
        agent, active_model = resolve_agent(
            override_source=(pref or {}).get("source") or None,
            override_model=(pref or {}).get("model") or None,
        )
    config  = {
        "configurable": {"thread_id": session_id},
        "recursion_limit": settings.max_tool_calls * 3 + 15,
    }
    sid     = _sid(session_id)

    tc_accum: dict[int, dict[str, Any]]      = {}
    pending_calls: dict[str, dict[str, Any]] = {}
    tool_calls_log: list[dict[str, Any]]     = []
    usage_meta: Any = None
    start = time.time()

    text_buf      = ""
    clean_buf     = ""
    response_text = ""  # full cleaned response — never cleared, used for DB persistence

    logger.info("{sep}", sep=_SEP)
    logger.info("▶  [{sid}]  USER: {msg}", sid=sid, msg=user_message)
    logger.info("{sep}", sep=_SEP)

    cancel_event = asyncio.Event()
    _cancel_events[session_id] = cancel_event

    def _flush_text_buf():
        nonlocal text_buf, clean_buf
        if text_buf.strip():
            cleaned = _clean(text_buf).strip()
            raw = text_buf.strip()
            if cleaned != raw:
                logger.debug(
                    "   [{sid}]  ✂   stripped artifacts | raw={raw!r} → clean={clean!r}",
                    sid=sid, raw=raw, clean=cleaned,
                )
            for line in (cleaned or raw).splitlines():
                if line.strip():
                    logger.info("   [{sid}]  🤖  {line}", sid=sid, line=line)
        text_buf = ""
        clean_buf = ""

    timed_out = False

    await maybe_summarize(agent, config, session_id)

    # DEBUG_LLM_CHUNKS=true in .env dumps every raw chunk's content + tool calls +
    # usage to the log. Useful when a model returns "(no response)" in the UI to
    # see whether the content is being stripped, wrapped in an unexpected format
    # (e.g. gpt-oss harmony channels), or is genuinely empty from the provider.
    import os as _os
    _debug_chunks = _os.environ.get("DEBUG_LLM_CHUNKS", "").lower() in ("1", "true", "yes")

    try:
        async with asyncio.timeout(settings.investigation_timeout):
            async for chunk, _meta in agent.astream(
                {"messages": [{"role": "user", "content": user_message}]},
                config=config,
                stream_mode="messages",
            ):
                if cancel_event.is_set():
                    logger.info("[{sid}]  cancelled by user", sid=sid)
                    yield f"data: {json.dumps({'type': 'cancelled'})}\n\n"
                    return
                if _debug_chunks:
                    _raw = getattr(chunk, "content", None)
                    _raw_type = type(_raw).__name__
                    _raw_preview = repr(_raw)[:400] if _raw is not None else "None"
                    _tcc = getattr(chunk, "tool_call_chunks", None)
                    _tc = getattr(chunk, "tool_calls", None)
                    _um = getattr(chunk, "usage_metadata", None)
                    logger.info(
                        "[{sid}] RAW chunk type={t} content={c}  tcc={tcc}  tc={tc}  usage={u}",
                        sid=sid, t=_raw_type, c=_raw_preview,
                        tcc=repr(_tcc)[:200] if _tcc else "-",
                        tc=repr(_tc)[:200] if _tc else "-",
                        u=repr(_um)[:200] if _um else "-",
                    )
                um = getattr(chunk, "usage_metadata", None)
                if um:
                    usage_meta = um

                for tcc in getattr(chunk, "tool_call_chunks", []) or []:
                    idx   = _field(tcc, "index", 0)
                    tc_id = _field(tcc, "id")
                    name  = _field(tcc, "name") or ""
                    args  = _field(tcc, "args") or ""
                    if idx not in tc_accum:
                        tc_accum[idx] = {"id": "", "name": "", "args_str": ""}
                    if tc_id:
                        tc_accum[idx]["id"] = tc_id
                    if name:
                        tc_accum[idx]["name"] += name
                    if args:
                        tc_accum[idx]["args_str"] += args

                # Complete tool_calls (non-streamed AIMessage) — DeepAgents often sends these
                # as a full message rather than chunks, so tool_call_chunks would be empty.
                for tc in getattr(chunk, "tool_calls", []) or []:
                    tc_id = _field(tc, "id") or ""
                    name  = _field(tc, "name") or ""
                    args  = _field(tc, "args") or {}
                    if tc_id and name:
                        pending_calls[tc_id] = {
                            "tool": name,
                            "args": args if isinstance(args, dict) else {},
                        }

                content = getattr(chunk, "content", "")
                visible = _extract_text(content)
                if visible:
                    if not getattr(chunk, "tool_call_id", None):
                        text_buf += visible
                        new_clean = _clean(text_buf)
                        delta = new_clean[len(clean_buf):]
                        if delta:
                            clean_buf = new_clean
                            response_text += delta
                            yield f"data: {json.dumps({'type': 'token', 'text': delta})}\n\n"

                tc_id = getattr(chunk, "tool_call_id", None)
                if tc_id:
                    _flush_text_buf()

                    for entry in tc_accum.values():
                        eid = entry["id"]
                        if eid:
                            try:
                                eargs: Any = json.loads(entry["args_str"]) if entry["args_str"] else {}
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

                    logger.info(
                        "   [{sid}]  🔧  {tool}({args})",
                        sid=sid, tool=call_info["tool"], args=call_info["args"],
                    )
                    if isinstance(result, dict) and "error" in result:
                        logger.warning("   [{sid}]  ⚠   error: {err}", sid=sid, err=result["error"])
                    elif isinstance(result, dict):
                        keys  = list(result.keys())
                        count = result.get("count", result.get("events", result.get("functions", "")))
                        logger.info(
                            "   [{sid}]  ✓   keys={keys}  count={count}",
                            sid=sid, keys=keys, count=count if isinstance(count, int) else "—",
                        )
                    else:
                        # gpt-oss / some providers return tool results as JSON arrays
                        # (e.g. CloudWatch metric data) — preserve them but don't try
                        # to .get() into a list. Log shape only.
                        logger.info(
                            "   [{sid}]  ✓   type={t}  len={n}",
                            sid=sid, t=type(result).__name__,
                            n=len(result) if hasattr(result, "__len__") else "—",
                        )

                    tool_calls_log.append({"tool": call_info["tool"], "args": call_info["args"], "result": result})
                    label = _pick_label(call_info["tool"])
                    yield f"data: {json.dumps({'type': 'tool_status', 'label': label})}\n\n"
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool': call_info['tool'], 'args': call_info['args'], 'result': result})}\n\n"

    except TimeoutError:
        timed_out = True
        logger.warning("[{sid}]  timed out after {timeout}s", sid=sid, timeout=settings.investigation_timeout)
        msg = (
            f"Investigation timed out after {settings.investigation_timeout}s. "
            "Try a narrower prompt or increase INVESTIGATION_TIMEOUT."
        )
        yield f"data: {json.dumps({'type': 'error', 'message': msg})}\n\n"

    except Exception as e:
        logger.error("[{sid}]  stream error: {err}", sid=sid, err=e)
        msg = (
            "Investigation hit the tool call limit. The agent gathered partial data — try a more specific query or increase MAX_TOOL_CALLS."
            if "recursion" in str(e).lower()
            else str(e)
        )
        yield f"data: {json.dumps({'type': 'error', 'message': msg})}\n\n"

    finally:
        _cancel_events.pop(session_id, None)

    _flush_text_buf()

    usage: dict[str, Any] = {
        "latency_ms": int((time.time() - start) * 1000),
        "model": active_model,
        "timed_out": timed_out,
    }
    if usage_meta:
        usage["input_tokens"]  = _field(usage_meta, "input_tokens", 0) or 0
        usage["output_tokens"] = _field(usage_meta, "output_tokens", 0) or 0
        # Capture reasoning tokens (gpt-oss, o1-family, Gemini thinking) for visibility
        # in the cost card and downstream analysis. We intentionally do NOT add them
        # to output_tokens for the cost calc here: providers differ on whether
        # output_tokens already includes reasoning (gpt-oss: YES — 53 total includes
        # 38 reasoning; Gemini: NO — but reasoning is also missing from the metadata,
        # which is the actual undercount bug). Per-provider normalization is tracked
        # in issue #59.
        details = _field(usage_meta, "output_token_details", None) or {}
        reasoning = _field(details, "reasoning", 0) or 0
        if reasoning and reasoning > 0:
            usage["reasoning_tokens"] = reasoning
    cost = calc_cost(
        usage["model"],
        usage.get("input_tokens", 0),
        usage.get("output_tokens", 0),
    )
    if cost is not None:
        usage["cost_usd"] = cost

    logger.info(
        "✓  [{sid}]  DONE  latency={lat}ms  in={inp}  out={out}",
        sid=sid,
        lat=usage["latency_ms"],
        inp=usage.get("input_tokens", "?"),
        out=usage.get("output_tokens", "?"),
    )
    logger.info("{sep}", sep=_SEP)

    await save_turn(session_id, user_message, response_text, tool_calls_log, usage)
    await notify_slack(session_id, tool_calls_log)

    follow_up_questions: list[str] = []
    for tc in tool_calls_log:
        if tc["tool"] == "submit_investigation":
            fq = tc["args"].get("follow_up_questions")
            if isinstance(fq, list):
                follow_up_questions = [q for q in fq if isinstance(q, str)]
            break

    yield f"data: {json.dumps({'type': 'done', 'usage': usage, 'follow_up_questions': follow_up_questions})}\n\n"


@router.post("/chat")
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    return StreamingResponse(
        _stream_chat(req.session_id, req.message.strip()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/chat/{session_id}")
async def cancel_chat(session_id: str) -> dict[str, bool]:
    """Signal the active stream for this session to stop at the next chunk."""
    event = _cancel_events.get(session_id)
    if event:
        event.set()
        return {"cancelled": True}
    return {"cancelled": False}
