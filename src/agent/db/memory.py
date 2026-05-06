"""In-memory backend — no persistence, ideal for CI and quick local testing."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from agent.db.base import DatabaseBackend


class MemoryBackend(DatabaseBackend):
    """All data lives in Python dicts. Everything is lost on process restart."""

    def __init__(self) -> None:
        self._checkpointer: Any = None
        self._sessions: dict[str, dict] = {}
        self._messages: dict[str, list[dict]] = defaultdict(list)
        self._tool_calls: dict[str, list[dict]] = defaultdict(list)
        self._usage: dict[str, list[dict]] = defaultdict(list)

    async def init(self) -> Any:
        from langgraph.checkpoint.memory import MemorySaver
        self._checkpointer = MemorySaver()
        logger.info("In-memory backend initialised (no persistence)")
        return self._checkpointer

    async def close(self) -> None:
        pass

    @property
    def checkpointer(self) -> Any:
        return self._checkpointer

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── App helpers ───────────────────────────────────────────────────────────

    async def upsert_session(
        self,
        session_id: str,
        model: str,
        aws_region: str,
        title: str | None = None,
    ) -> None:
        if session_id in self._sessions:
            self._sessions[session_id]["last_active_at"] = self._now()
            self._sessions[session_id]["model"] = model
        else:
            self._sessions[session_id] = {
                "id": session_id,
                "title": title,
                "model": model,
                "aws_region": aws_region,
                "created_at": self._now(),
                "last_active_at": self._now(),
                "is_deleted": False,
            }

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> str:
        msg_id = str(uuid.uuid4())
        self._messages[session_id].append({
            "id": msg_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "created_at": self._now(),
        })
        return msg_id

    async def save_tool_call(
        self,
        session_id: str,
        message_id: str | None,
        tool_name: str,
        args: dict,
        result: dict,
        duration_ms: int | None = None,
    ) -> None:
        error = result.get("error") if isinstance(result, dict) else None
        self._tool_calls[session_id].append({
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "message_id": message_id,
            "tool_name": tool_name,
            "args": args,
            "result": result,
            "error": error,
            "duration_ms": duration_ms,
            "created_at": self._now(),
        })

    async def save_usage_event(
        self,
        session_id: str,
        message_id: str | None,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float | None,
        latency_ms: int,
        tool_call_count: int,
    ) -> None:
        self._usage[session_id].append({
            "session_id": session_id,
            "message_id": message_id,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "latency_ms": latency_ms,
            "tool_call_count": tool_call_count,
        })

    async def list_sessions(self) -> list[dict]:
        active = [s for s in self._sessions.values() if not s.get("is_deleted")]
        return sorted(active, key=lambda s: s["last_active_at"], reverse=True)

    async def get_messages(self, session_id: str) -> list[dict]:
        session = self._sessions.get(session_id)
        if session is None or session.get("is_deleted"):
            return []

        tc_by_msg: dict[str, list] = defaultdict(list)
        for tc in self._tool_calls.get(session_id, []):
            if tc["message_id"]:
                tc_by_msg[tc["message_id"]].append({
                    "tool_name": tc["tool_name"],
                    "args": tc["args"],
                    "result": tc["result"],
                    "error": tc["error"],
                })

        usage_by_msg = {
            u["message_id"]: {
                "model": u["model"],
                "input_tokens": u["input_tokens"],
                "output_tokens": u["output_tokens"],
                "cost_usd": u["cost_usd"],
                "latency_ms": u["latency_ms"],
            }
            for u in self._usage.get(session_id, [])
            if u["message_id"]
        }

        result = []
        for msg in self._messages.get(session_id, []):
            item: dict = {
                "id": msg["id"],
                "role": msg["role"],
                "content": msg["content"],
                "created_at": msg["created_at"],
                "tool_calls": [],
                "usage": None,
            }
            if msg["role"] == "assistant":
                item["tool_calls"] = tc_by_msg.get(msg["id"], [])
                item["usage"] = usage_by_msg.get(msg["id"])
            result.append(item)
        return result

    async def delete_session(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id]["is_deleted"] = True

    # ── Analytics ─────────────────────────────────────────────────────────────

    async def get_dashboard_stats(self) -> dict:
        active = [s for s in self._sessions.values() if not s.get("is_deleted")]
        all_tc = [tc for tcs in self._tool_calls.values() for tc in tcs]
        all_usage = [u for us in self._usage.values() for u in us]
        all_msgs = [m for ms in self._messages.values() for m in ms]

        total_cost   = sum(u["cost_usd"] or 0 for u in all_usage)
        avg_latency  = (
            sum(u["latency_ms"] for u in all_usage) // len(all_usage)
            if all_usage else 0
        )

        return {
            "summary": {
                "total_sessions":    len(active),
                "total_queries":     sum(1 for m in all_msgs if m["role"] == "user"),
                "total_tool_calls":  len(all_tc),
                "total_tool_errors": sum(1 for tc in all_tc if tc.get("error")),
                "total_input_tokens":  sum(u["input_tokens"] for u in all_usage),
                "total_output_tokens": sum(u["output_tokens"] for u in all_usage),
                "total_cost_usd":    total_cost,
                "avg_latency_ms":    avg_latency,
            },
            "activity": [],
            "top_tools": [],
            "service_breakdown": [],
            "recent_sessions": [],
            "root_causes": [],
        }

    async def get_history_stats(self, days: int = 30) -> dict:
        return {
            "days": days,
            "top_alarms": [],
            "top_lambdas": [],
            "recurring_errors": [],
            "trend": [],
        }

    async def search_sessions(self, query: str, limit: int = 10) -> list[dict]:
        if not query.strip():
            return []
        q = query.lower()
        results = []
        for s in self._sessions.values():
            if s.get("is_deleted"):
                continue
            title_match = q in (s.get("title") or "").lower()
            msgs = self._messages.get(s["id"], [])
            snippet = ""
            content_match = False
            for m in msgs:
                if m["role"] == "user":
                    if not snippet:
                        snippet = m["content"][:200]
                    if q in m["content"].lower():
                        content_match = True
                        break
            if title_match or content_match:
                results.append({
                    "id": s["id"],
                    "title": s.get("title"),
                    "last_active_at": s["last_active_at"],
                    "model": s.get("model"),
                    "snippet": snippet,
                })
        results.sort(key=lambda x: x["last_active_at"], reverse=True)
        return results[:min(limit, 20)]
