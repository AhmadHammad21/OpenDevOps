"""FastAPI app — chat endpoint with per-session message history."""

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from agent.config import settings
from agent.prompts import SYSTEM_PROMPT
from api.sessions import append_messages, clear_session, get_history
from openai import OpenAI
from tools.base import BaseTool
from tools.cloudtrail import ALL_CLOUDTRAIL_TOOLS
from tools.cloudwatch import ALL_CLOUDWATCH_TOOLS
from tools.ec2 import ALL_EC2_TOOLS
from tools.ecs import ALL_ECS_TOOLS
from tools.iam import ALL_IAM_TOOLS
from tools.lambda_ import ALL_LAMBDA_TOOLS
from tools.rds import ALL_RDS_TOOLS

logger = logging.getLogger(__name__)

app = FastAPI(title="OpenDevOps Agent", version="0.1.0")

ALL_TOOLS: list[BaseTool] = (
    ALL_CLOUDWATCH_TOOLS
    + ALL_CLOUDTRAIL_TOOLS
    + ALL_ECS_TOOLS
    + ALL_LAMBDA_TOOLS
    + ALL_EC2_TOOLS
    + ALL_RDS_TOOLS
    + ALL_IAM_TOOLS
)
_TOOL_MAP: dict[str, BaseTool] = {t.name: t for t in ALL_TOOLS}
_TOOLS_SCHEMA = [t.as_openai_tool() for t in ALL_TOOLS]

_STATIC = Path(__file__).parent.parent.parent / "frontend"


class ChatRequest(BaseModel):
    session_id: str
    message: str


def _openai_client() -> OpenAI:
    return OpenAI(api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url)


def _run_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    tool = _TOOL_MAP.get(name)
    if not tool:
        return {"error": f"Unknown tool: {name}"}
    return tool.run(**args)


async def _stream_chat(session_id: str, user_message: str):
    """Run the ReAct loop and stream tokens back as SSE."""
    client = _openai_client()
    history = get_history(session_id)

    if not history:
        append_messages(session_id, {"role": "system", "content": SYSTEM_PROMPT})
        history = get_history(session_id)

    append_messages(session_id, {"role": "user", "content": user_message})
    history = get_history(session_id)

    tool_calls_made = 0

    while tool_calls_made <= settings.max_tool_calls:
        # Stream the LLM response
        stream = client.chat.completions.create(
            model=settings.openrouter_model,
            messages=history,
            tools=_TOOLS_SCHEMA,
            tool_choice="auto",
            stream=True,
        )

        full_content = ""
        pending_tool_calls: list[dict[str, Any]] = []
        finish_reason = None

        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue

            finish_reason = chunk.choices[0].finish_reason or finish_reason

            # Stream text tokens to the client
            if delta.content:
                full_content += delta.content
                yield f"data: {json.dumps({'type': 'token', 'text': delta.content})}\n\n"

            # Accumulate tool call chunks
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    while len(pending_tool_calls) <= idx:
                        pending_tool_calls.append({"id": "", "name": "", "arguments": ""})
                    if tc.id:
                        pending_tool_calls[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            pending_tool_calls[idx]["name"] += tc.function.name
                        if tc.function.arguments:
                            pending_tool_calls[idx]["arguments"] += tc.function.arguments

        # No tool calls — final answer
        if not pending_tool_calls or finish_reason == "stop":
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": full_content}
            append_messages(session_id, assistant_msg)
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # Build assistant message with tool_calls for the next turn
        tool_call_objs = [
            {
                "id": tc["id"],
                "type": "function",
                "function": {"name": tc["name"], "arguments": tc["arguments"]},
            }
            for tc in pending_tool_calls
        ]
        assistant_msg = {"role": "assistant", "content": full_content or None, "tool_calls": tool_call_objs}
        append_messages(session_id, assistant_msg)

        # Execute each tool and append results
        tool_results = []
        for tc in pending_tool_calls:
            try:
                args = json.loads(tc["arguments"])
            except json.JSONDecodeError:
                args = {}

            result = _run_tool(tc["name"], args)
            tool_calls_made += 1

            yield f"data: {json.dumps({'type': 'tool_call', 'tool': tc['name'], 'args': args, 'result': result})}\n\n"

            tool_results.append(
                {"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(result)}
            )

        append_messages(session_id, *tool_results)

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
    clear_session(session_id)
    return {"cleared": session_id}
