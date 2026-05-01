"""OpenDevOps MCP Server — exposes the agent as an MCP server.

Tools available to MCP clients (Claude Desktop, Cursor, etc.):
  - investigate  : full root-cause investigation with AWS tools
  - ask          : freeform Q&A with AWS context
  - list_sessions: recent investigation sessions from the DB

Run with:
    uv run devops-agent mcp          # stdio transport (Claude Desktop)
    uv run devops-agent mcp --http   # HTTP+SSE transport (port 8001)
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from typing import Any

from fastmcp import FastMCP
from loguru import logger

from agent.config import settings

mcp = FastMCP(
    name="OpenDevOps Agent",
    instructions=(
        "Use `investigate` when the user reports an AWS incident, alarm, or anomaly. "
        "Use `ask` for general AWS/DevOps questions. "
        "Use `list_sessions` to browse previous investigations."
    ),
)


async def _init() -> None:
    """Initialise DB + agent once on first use."""
    from agent.core import get_agent, init_agent
    from agent.db import db
    try:
        get_agent()
    except RuntimeError:
        checkpointer = await db.init()
        init_agent(checkpointer)


async def _run_agent(prompt: str) -> dict[str, Any]:
    """Run the agent and return the submit_investigation args (or a plain text fallback)."""
    await _init()
    from agent.core import get_agent

    thread_id = str(uuid.uuid4())
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": settings.max_tool_calls * 3 + 15,
    }
    result = await get_agent().ainvoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config=config,
    )
    # Prefer structured submit_investigation result
    for msg in reversed(result.get("messages", [])):
        for tc in getattr(msg, "tool_calls", []) or []:
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
            args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
            if name == "submit_investigation":
                return {"type": "investigation", "session_id": thread_id, **args}
    # Fall back to last assistant message text
    for msg in reversed(result.get("messages", [])):
        content = getattr(msg, "content", None)
        if content and not getattr(msg, "tool_calls", None):
            return {"type": "text", "session_id": thread_id, "text": str(content)}
    return {"type": "text", "session_id": thread_id, "text": "No result produced."}


def _format_investigation(r: dict[str, Any]) -> str:
    lines = [
        f"## Root Cause — {r.get('root_cause_category', 'UNKNOWN')}",
        f"**Confidence:** {r.get('confidence', 'LOW')}",
        f"**Session:** {r.get('session_id', '')[:8]}",
        "",
        r.get("root_cause_summary", ""),
    ]
    if r.get("evidence"):
        lines += ["", "### Evidence"]
        lines += [f"- {e}" for e in r["evidence"]]
    if r.get("mitigation_steps"):
        lines += ["", "### Mitigation Steps"]
        lines += [f"{i+1}. {s}" for i, s in enumerate(r["mitigation_steps"])]
    if r.get("validation_steps"):
        lines += ["", "### Validation Steps"]
        lines += [f"- {s}" for s in r["validation_steps"]]
    if r.get("services_affected"):
        lines += ["", f"**Services affected:** {', '.join(r['services_affected'])}"]
    if r.get("recommended_follow_up"):
        lines += ["", f"**Follow-up:** {r['recommended_follow_up']}"]
    return "\n".join(lines)


@mcp.tool()
async def investigate(
    description: str,
    alarm_name: str = "",
    service: str = "",
) -> str:
    """Investigate an AWS incident, alarm, or anomaly and return a structured root-cause report.

    Args:
        description: What is going wrong — e.g. "high error rate on payment Lambda".
        alarm_name:  Optional CloudWatch alarm name to focus the investigation.
        service:     Optional service name (ECS service, Lambda function, etc.).
    """
    prompt = description
    if alarm_name:
        prompt += f"\nAlarm: {alarm_name}"
    if service:
        prompt += f"\nService: {service}"

    logger.info("MCP investigate: {}", description[:80])
    result = await _run_agent(prompt)

    if result["type"] == "investigation":
        return _format_investigation(result)
    return result.get("text", "Investigation produced no output.")


@mcp.tool()
async def ask(question: str) -> str:
    """Ask a freeform AWS / DevOps question. No structured output — just a direct answer.

    Args:
        question: Any AWS or DevOps question, e.g. "why would a Lambda suddenly throttle?"
    """
    logger.info("MCP ask: {}", question[:80])
    result = await _run_agent(question)
    if result["type"] == "text":
        return result["text"]
    return _format_investigation(result)


@mcp.tool()
async def list_sessions(limit: int = 10) -> str:
    """List the most recent investigation sessions.

    Args:
        limit: Number of sessions to return (max 50).
    """
    await _init()
    from agent.db import db

    limit = min(limit, 50)
    sessions = await db.list_sessions(limit=limit)
    if not sessions:
        return "No sessions found."
    lines = ["## Recent Sessions", ""]
    for s in sessions:
        title = s.get("title") or "Untitled"
        sid   = s.get("id", "")[:8]
        when  = s.get("last_active_at", "")[:10]
        model = s.get("model", "")
        lines.append(f"- **{title}** · `{sid}` · {when} · {model}")
    return "\n".join(lines)


def run_stdio() -> None:
    """Start the MCP server on stdio (for Claude Desktop / Cursor)."""
    mcp.run(transport="stdio")


def run_http(port: int = 8001) -> None:
    """Start the MCP server over HTTP+SSE."""
    mcp.run(transport="sse", host="0.0.0.0", port=port)
