"""FastAPI app — chat endpoint using DeepAgents with per-session LangGraph threads."""

import json
import logging
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from agent.core import get_agent

logger = logging.getLogger(__name__)

app = FastAPI(title="OpenDevOps Agent", version="0.1.0")

_STATIC = Path(__file__).parent.parent.parent / "frontend"


class ChatRequest(BaseModel):
    session_id: str
    message: str


def _field(obj: Any, key: str, default: Any = None) -> Any:
    """Read a field from either a dict or a typed object (e.g. ToolCallChunk)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


async def _stream_chat(session_id: str, user_message: str):
    """Stream SSE events to the frontend.

    stream_mode='messages' yields (BaseMessageChunk, metadata) tuples.
    Tool call args are buffered by tool_call_id (accumulated from
    tool_call_chunks) so each tool event has {tool, args, result}.
    Token usage and latency are sent in the final 'done' event.
    """
    agent = get_agent()
    config = {"configurable": {"thread_id": session_id}}

    tc_accum: dict[int, dict[str, Any]] = {}
    pending_calls: dict[str, dict[str, Any]] = {}
    usage_meta: Any = None
    start = time.time()

    try:
        async for chunk, _meta in agent.astream(
            {"messages": [{"role": "user", "content": user_message}]},
            config=config,
            stream_mode="messages",
        ):
            # ── Capture token usage from the last chunk that has it ──
            um = getattr(chunk, "usage_metadata", None)
            if um:
                usage_meta = um

            # ── Accumulate tool_call_chunks (args stream as JSON fragments) ──
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

            # ── Stream text tokens ──
            content = getattr(chunk, "content", "")
            if content and isinstance(content, str):
                if not getattr(chunk, "tool_call_id", None):
                    yield f"data: {json.dumps({'type': 'token', 'text': content})}\n\n"

            # ── Tool result (ToolMessage) ──
            tc_id = getattr(chunk, "tool_call_id", None)
            if tc_id:
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
                    "tool_call session=%s tool=%s args=%s result_keys=%s",
                    session_id,
                    call_info["tool"],
                    call_info["args"],
                    list(result.keys()) if isinstance(result, dict) else type(result).__name__,
                )
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': call_info['tool'], 'args': call_info['args'], 'result': result})}\n\n"

    except Exception as e:
        logger.error("stream_chat error: %s", e)
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    usage: dict[str, Any] = {"latency_ms": int((time.time() - start) * 1000)}
    if usage_meta:
        usage["input_tokens"]  = _field(usage_meta, "input_tokens", 0) or 0
        usage["output_tokens"] = _field(usage_meta, "output_tokens", 0) or 0

    yield f"data: {json.dumps({'type': 'done', 'usage': usage})}\n\n"


@app.get("/", response_class=HTMLResponse)
async def index():
    html_file = _STATIC / "index.html"
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))


@app.post("/chat")
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    return StreamingResponse(
        _stream_chat(req.session_id, req.message.strip()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    return {"cleared": session_id}
