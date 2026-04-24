"""FastAPI app — chat endpoint using DeepAgents with per-session LangGraph threads."""

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel

from agent.config import settings
from agent.core import get_agent


class _InterceptHandler(logging.Handler):
    """Forward stdlib logging records to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


# Route all stdlib logging (tools, LangChain, uvicorn access) through loguru
logging.basicConfig(handlers=[_InterceptHandler()], level=logging.INFO, force=True)
for _name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
    logging.getLogger(_name).handlers = [_InterceptHandler()]

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


_SEP = "─" * 60

# Strip DeepAgents channel markers and lone artifact words the model leaks into output.
# <channel|thought> / <channel|>thought  — DeepAgents routing syntax, never legitimate content.
# ^thought$  — the word "thought" alone on its own line (artifact preamble before tool calls).
#              Safe because real sentences never consist of just "thought" with nothing else.
_CHANNEL_RE = re.compile(
    r"<channel\|[^>]*>"        # <channel|thought>
    r"|<channel\|>[a-zA-Z_]*\s*"  # <channel|>thought
    r"|^thought\s*$",          # bare "thought" on its own line
    re.IGNORECASE | re.MULTILINE,
)


def _sid(session_id: str) -> str:
    return session_id[:8]


def _clean(text: str) -> str:
    return _CHANNEL_RE.sub("", text)


async def _stream_chat(session_id: str, user_message: str):
    """Stream SSE events to the frontend."""
    agent   = get_agent()
    config  = {"configurable": {"thread_id": session_id}}
    sid     = _sid(session_id)

    tc_accum: dict[int, dict[str, Any]]    = {}
    pending_calls: dict[str, dict[str, Any]] = {}
    usage_meta: Any = None
    start = time.time()

    # text_buf: raw model output (logged as-is so you see exactly what the model emits)
    # clean_buf: stripped version that is actually sent to the frontend
    text_buf = ""
    clean_buf = ""

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

    try:
        async for chunk, _meta in agent.astream(
            {"messages": [{"role": "user", "content": user_message}]},
            config=config,
            stream_mode="messages",
        ):
            um = getattr(chunk, "usage_metadata", None)
            if um:
                usage_meta = um

            # Accumulate tool_call_chunks
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

            # Stream text tokens — buffer raw for logging, send only cleaned delta to frontend
            content = getattr(chunk, "content", "")
            if content and isinstance(content, str):
                if not getattr(chunk, "tool_call_id", None):
                    text_buf += content
                    new_clean = _clean(text_buf)
                    delta = new_clean[len(clean_buf):]
                    if delta:
                        clean_buf = new_clean
                        yield f"data: {json.dumps({'type': 'token', 'text': delta})}\n\n"

            # Tool result (ToolMessage)
            tc_id = getattr(chunk, "tool_call_id", None)
            if tc_id:
                _flush_text_buf()  # log any reasoning text before the tool result

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
                    logger.warning(
                        "   [{sid}]  ⚠   error: {err}",
                        sid=sid, err=result["error"],
                    )
                else:
                    keys = list(result.keys()) if isinstance(result, dict) else type(result).__name__
                    count = result.get("count", result.get("events", result.get("functions", "")))
                    logger.info(
                        "   [{sid}]  ✓   keys={keys}  count={count}",
                        sid=sid, keys=keys, count=count if isinstance(count, int) else "—",
                    )

                yield f"data: {json.dumps({'type': 'tool_call', 'tool': call_info['tool'], 'args': call_info['args'], 'result': result})}\n\n"

    except Exception as e:
        logger.error("[{sid}]  stream error: {err}", sid=sid, err=e)
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    _flush_text_buf()  # log the final answer text

    usage: dict[str, Any] = {
        "latency_ms": int((time.time() - start) * 1000),
        "model": settings.openrouter_model,
    }
    if usage_meta:
        usage["input_tokens"]  = _field(usage_meta, "input_tokens", 0) or 0
        usage["output_tokens"] = _field(usage_meta, "output_tokens", 0) or 0

    logger.info(
        "✓  [{sid}]  DONE  latency={lat}ms  in={inp}  out={out}",
        sid=sid,
        lat=usage["latency_ms"],
        inp=usage.get("input_tokens", "?"),
        out=usage.get("output_tokens", "?"),
    )
    logger.info("{sep}", sep=_SEP)

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
