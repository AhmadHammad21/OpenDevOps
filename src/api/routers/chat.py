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

from config import settings
from agent.core import get_agent
from agent.turns import calc_cost, save_turn, notify_slack
from models.chat import ChatRequest
from api.streaming_labels import STREAMING_LABELS

router = APIRouter(tags=["chat"])


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




async def _stream_chat(session_id: str, user_message: str):
    """Stream SSE events to the frontend."""
    agent   = get_agent()
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

    try:
        async with asyncio.timeout(settings.investigation_timeout):
            async for chunk, _meta in agent.astream(
                {"messages": [{"role": "user", "content": user_message}]},
                config=config,
                stream_mode="messages",
            ):
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
                if content and isinstance(content, str):
                    if not getattr(chunk, "tool_call_id", None):
                        text_buf += content
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
                    else:
                        keys  = list(result.keys()) if isinstance(result, dict) else type(result).__name__
                        count = result.get("count", result.get("events", result.get("functions", "")))
                        logger.info(
                            "   [{sid}]  ✓   keys={keys}  count={count}",
                            sid=sid, keys=keys, count=count if isinstance(count, int) else "—",
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

    _flush_text_buf()

    usage: dict[str, Any] = {
        "latency_ms": int((time.time() - start) * 1000),
        "model": settings.llm_model,
        "timed_out": timed_out,
    }
    if usage_meta:
        usage["input_tokens"]  = _field(usage_meta, "input_tokens", 0) or 0
        usage["output_tokens"] = _field(usage_meta, "output_tokens", 0) or 0
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

    yield f"data: {json.dumps({'type': 'done', 'usage': usage})}\n\n"


@router.post("/chat")
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    return StreamingResponse(
        _stream_chat(req.session_id, req.message.strip()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
