"""FastAPI app — chat endpoint using DeepAgents with per-session LangGraph threads."""

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from agent.core import get_agent


def _field(obj: Any, key: str, default: Any = None) -> Any:
    """Read a field from either a dict or a typed object (e.g. ToolCallChunk)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

logger = logging.getLogger(__name__)

app = FastAPI(title="OpenDevOps Agent", version="0.1.0")

_STATIC = Path(__file__).parent.parent.parent / "frontend"


class ChatRequest(BaseModel):
    session_id: str
    message: str


async def _stream_chat(session_id: str, user_message: str):
    """Stream SSE events to the frontend.

    stream_mode='messages' yields (BaseMessageChunk, metadata) tuples.
    We buffer tool call args from AIMessageChunks by tool_call_id so each
    tool event includes {tool, args, result} — the shape addCall() expects.
    """
    agent = get_agent()
    config = {"configurable": {"thread_id": session_id}}

    # Accumulate partial tool_call_chunks: index → {id, name, args_str}
    tc_accum: dict[int, dict[str, Any]] = {}
    # Finalized tool calls keyed by tool_call_id
    pending_calls: dict[str, dict[str, Any]] = {}

    try:
        async for chunk, _meta in agent.astream(
            {"messages": [{"role": "user", "content": user_message}]},
            config=config,
            stream_mode="messages",
        ):
            # ── Accumulate streaming tool call fragments from AIMessageChunk ──
            # tool_call_chunks may be dicts or typed ToolCallChunk objects
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

            # ── Complete tool_calls on a final AIMessage (not a chunk) ──
            for tc in getattr(chunk, "tool_calls", []) or []:
                tc_id = _field(tc, "id") or ""
                if tc_id:
                    pending_calls[tc_id] = {
                        "tool": _field(tc, "name") or "",
                        "args": _field(tc, "args") or {},
                    }

            # ── Stream text tokens ──
            content = getattr(chunk, "content", "")
            if content and isinstance(content, str):
                # Skip ToolMessages (they have tool_call_id)
                if not getattr(chunk, "tool_call_id", None):
                    yield f"data: {json.dumps({'type': 'token', 'text': content})}\n\n"

            # ── Tool result (ToolMessage) ──
            tc_id = getattr(chunk, "tool_call_id", None)
            if tc_id:
                # Flush any accumulated chunks into pending_calls
                for entry in tc_accum.values():
                    eid = entry["id"]
                    if eid and eid not in pending_calls:
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

                yield f"data: {json.dumps({'type': 'tool_call', 'tool': call_info['tool'], 'args': call_info['args'], 'result': result})}\n\n"

    except Exception as e:
        logger.error("stream_chat error: %s", e)
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


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
