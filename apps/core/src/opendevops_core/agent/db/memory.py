"""In-memory backend — no persistence, ideal for CI and quick local testing."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger

from opendevops_core.agent.db.base import DatabaseBackend


class MemoryBackend(DatabaseBackend):
    """All data lives in Python dicts. Everything is lost on process restart."""

    def __init__(self) -> None:
        self._checkpointer: Any = None
        self._sessions: dict[str, dict] = {}
        self._messages: dict[str, list[dict]] = defaultdict(list)
        self._tool_calls: dict[str, list[dict]] = defaultdict(list)
        self._usage: dict[str, list[dict]] = defaultdict(list)
        self._orgs: dict[str, dict] = {}
        self._users: dict[str, dict] = {}
        self._alerts: list[dict] = []
        self._incident_claims: dict[str, dict] = {}
        self._app_config: dict[str, dict] = {}

    async def init(self) -> Any:
        from langgraph.checkpoint.memory import MemorySaver

        self._checkpointer = MemorySaver()
        logger.warning(
            "In-memory backend active — all data is lost on restart and memory grows "
            "unboundedly. Use CHECKPOINT_BACKEND=sqlite or postgres for anything beyond "
            "quick testing."
        )
        return self._checkpointer

    async def close(self) -> None:
        pass

    @property
    def checkpointer(self) -> Any:
        return self._checkpointer

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    # ── App helpers ───────────────────────────────────────────────────────────

    async def upsert_session(
        self,
        session_id: str,
        model: str,
        aws_region: str,
        title: str | None = None,
        source: str = "chat",
        org_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        if session_id in self._sessions:
            self._sessions[session_id]["last_active_at"] = self._now()
            self._sessions[session_id]["model"] = model
            if source == "chat":
                self._sessions[session_id]["user_interacted"] = True
            self._sessions[session_id].setdefault("org_id", org_id)
            self._sessions[session_id].setdefault("user_id", user_id)
        else:
            self._sessions[session_id] = {
                "id": session_id,
                "title": title,
                "model": model,
                "aws_region": aws_region,
                "source": source,
                "org_id": org_id,
                "user_id": user_id,
                "user_interacted": source == "chat",
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
        self._messages[session_id].append(
            {
                "id": msg_id,
                "session_id": session_id,
                "role": role,
                "content": content,
                "metadata": metadata or {},
                "created_at": self._now(),
            }
        )
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
        self._tool_calls[session_id].append(
            {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "message_id": message_id,
                "tool_name": tool_name,
                "args": args,
                "result": result,
                "error": error,
                "duration_ms": duration_ms,
                "created_at": self._now(),
            }
        )

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
        metadata: dict | None = None,
    ) -> None:
        self._usage[session_id].append(
            {
                "session_id": session_id,
                "message_id": message_id,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd,
                "latency_ms": latency_ms,
                "tool_call_count": tool_call_count,
                "metadata": metadata or {},
            }
        )

    async def list_sessions(
        self, limit: int = 15, offset: int = 0, org_id: str | None = None
    ) -> list[dict]:
        active = [
            s
            for s in self._sessions.values()
            if not s.get("is_deleted")
            and (s.get("source", "chat") == "chat" or s.get("user_interacted", False))
            and (org_id is None or s.get("org_id") == org_id)
        ]
        sorted_sessions = sorted(active, key=lambda s: s["last_active_at"], reverse=True)
        return sorted_sessions[offset : offset + limit]

    async def get_messages(self, session_id: str, org_id: str | None = None) -> list[dict]:
        session = self._sessions.get(session_id)
        if session is None or session.get("is_deleted"):
            return []
        if org_id is not None and session.get("org_id") != org_id:
            return []

        tc_by_msg: dict[str, list] = defaultdict(list)
        for tc in self._tool_calls.get(session_id, []):
            if tc["message_id"]:
                tc_by_msg[tc["message_id"]].append(
                    {
                        "tool_name": tc["tool_name"],
                        "args": tc["args"],
                        "result": tc["result"],
                        "error": tc["error"],
                    }
                )

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

    async def rename_session(self, session_id: str, title: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id]["title"] = title

    # ── Analytics ─────────────────────────────────────────────────────────────

    async def get_dashboard_stats(self) -> dict:
        active = [s for s in self._sessions.values() if not s.get("is_deleted")]
        all_tc = [tc for tcs in self._tool_calls.values() for tc in tcs]
        all_usage = [u for us in self._usage.values() for u in us]
        all_msgs = [m for ms in self._messages.values() for m in ms]

        total_cost = sum(u["cost_usd"] or 0 for u in all_usage)
        avg_latency = sum(u["latency_ms"] for u in all_usage) // len(all_usage) if all_usage else 0
        summ_events = [
            u
            for u in all_usage
            if isinstance(u.get("metadata"), dict) and u["metadata"].get("summarization")
        ]

        return {
            "summary": {
                "total_sessions": len(active),
                "total_queries": sum(1 for m in all_msgs if m["role"] == "user"),
                "total_tool_calls": len(all_tc),
                "total_tool_errors": sum(1 for tc in all_tc if tc.get("error")),
                "total_input_tokens": sum(u["input_tokens"] for u in all_usage),
                "total_output_tokens": sum(u["output_tokens"] for u in all_usage),
                "total_cost_usd": total_cost,
                "avg_latency_ms": avg_latency,
                "total_summarizations": len(summ_events),
                "total_chars_compacted": sum(
                    e["metadata"].get("chars_removed", 0) for e in summ_events
                ),
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

    # ── User / auth ─────────────────────────────────────────────────────────

    async def count_users(self) -> int:
        return sum(1 for user in self._users.values() if user.get("password_hash"))

    async def get_user_by_email(self, email: str) -> dict | None:
        for user in self._users.values():
            if user["email"] == email:
                return dict(user)
        return None

    async def get_user_by_id(self, user_id: str) -> dict | None:
        user = self._users.get(user_id)
        return dict(user) if user else None

    async def create_org(self, name: str, slug: str) -> dict | None:
        for org in self._orgs.values():
            if org["slug"] == slug:
                org["name"] = name
                return dict(org)
        org_id = str(uuid.uuid4())
        org = {"id": org_id, "name": name, "slug": slug, "created_at": self._now()}
        self._orgs[org_id] = org
        return dict(org)

    async def get_first_org(self) -> dict | None:
        if not self._orgs:
            return None
        org = sorted(self._orgs.values(), key=lambda item: item["created_at"])[0]
        return dict(org)

    async def create_user(
        self,
        email: str,
        name: str,
        password_hash: str,
        role: str,
        org_id: str | None = None,
    ) -> dict | None:
        if await self.get_user_by_email(email):
            return None
        user_id = str(uuid.uuid4())
        user = {
            "id": user_id,
            "email": email,
            "name": name,
            "password_hash": password_hash,
            "role": role,
            "org_id": org_id,
            "created_at": self._now(),
        }
        self._users[user_id] = user
        return {k: v for k, v in user.items() if k != "password_hash"}

    async def list_users(self) -> list[dict]:
        users = sorted(self._users.values(), key=lambda item: item["created_at"])
        return [{k: v for k, v in user.items() if k != "password_hash"} for user in users]

    async def update_user(self, user_id: str, **fields: Any) -> dict | None:
        user = self._users.get(user_id)
        if not user:
            return None
        for key in ("name", "role", "password_hash"):
            if key in fields:
                user[key] = fields[key]
        return {k: v for k, v in user.items() if k != "password_hash"}

    async def assign_org_to_users_without_org(self, org_id: str) -> None:
        for user in self._users.values():
            if not user.get("org_id"):
                user["org_id"] = org_id

    async def delete_user(self, user_id: str) -> None:
        self._users.pop(user_id, None)

    # ── Alerts ────────────────────────────────────────────────────────────────

    async def add_alert(
        self,
        service: str,
        error: str,
        resolution: str,
        confidence: str,
        sns_sent: bool,
        dedup_key: str | None = None,
        status: str = "completed",
        session_id: str | None = None,
        trigger_source: str | None = None,
    ) -> str:
        alert_id = str(uuid.uuid4())
        self._alerts.append(
            {
                "id": alert_id,
                "service": service,
                "error": error,
                "resolution": resolution,
                "confidence": confidence,
                "sns_sent": sns_sent,
                "timestamp": self._now(),
                "dedup_key": dedup_key,
                "status": status,
                "session_id": session_id,
                "trigger_source": trigger_source,
                "notifications": [],
            }
        )
        return alert_id

    async def add_notification(
        self,
        alert_id: str,
        channel: str,
        status: str = "attempted",
        error: str | None = None,
    ) -> None:
        for alert in self._alerts:
            if alert["id"] == alert_id:
                alert.setdefault("notifications", []).append(
                    {
                        "channel": channel,
                        "status": status,
                        "error": error,
                        "sent_at": self._now(),
                    }
                )
                return

    async def is_recent_alert(self, dedup_key: str, within_minutes: int = 3) -> bool:
        cutoff = datetime.now(UTC) - timedelta(minutes=within_minutes)
        for alert in self._alerts:
            if alert.get("dedup_key") != dedup_key:
                continue
            try:
                if datetime.fromisoformat(alert["timestamp"]) > cutoff:
                    return True
            except Exception:
                continue
        return False

    async def claim_incident(
        self,
        incident_key: str,
        trigger_source: str,
        within_minutes: int = 3,
    ) -> bool:
        now = datetime.now(UTC)
        existing = self._incident_claims.get(incident_key)
        if existing:
            last = existing.get("completed_at") or existing.get("claimed_at") or now
            if now - last <= timedelta(minutes=within_minutes):
                return False
        self._incident_claims[incident_key] = {
            "trigger_source": trigger_source,
            "status": "claimed",
            "session_id": None,
            "claimed_at": now,
            "completed_at": None,
        }
        return True

    async def complete_incident(
        self,
        incident_key: str,
        status: str = "completed",
        session_id: str | None = None,
    ) -> None:
        claim = self._incident_claims.setdefault(
            incident_key,
            {"trigger_source": "unknown", "claimed_at": datetime.now(UTC)},
        )
        claim.update(
            {
                "status": status,
                "session_id": session_id,
                "completed_at": datetime.now(UTC),
            }
        )

    async def release_incident(self, incident_key: str) -> None:
        if self._incident_claims.get(incident_key, {}).get("status") == "claimed":
            self._incident_claims.pop(incident_key, None)

    async def is_incident_claimed(self, incident_key: str, within_minutes: int = 3) -> bool:
        claim = self._incident_claims.get(incident_key)
        if not claim:
            return False
        last = claim.get("completed_at") or claim.get("claimed_at")
        return bool(last and datetime.now(UTC) - last <= timedelta(minutes=within_minutes))

    async def get_alerts(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._alerts))[: min(limit, 200)]

    async def get_alert(self, alert_id: str) -> dict | None:
        for a in self._alerts:
            if a["id"] == alert_id:
                return a
        return None

    async def get_app_config(self, key: str) -> dict | None:
        return self._app_config.get(key)

    async def set_app_config(self, key: str, value: dict) -> None:
        self._app_config[key] = value

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
                results.append(
                    {
                        "id": s["id"],
                        "title": s.get("title"),
                        "last_active_at": s["last_active_at"],
                        "model": s.get("model"),
                        "snippet": snippet,
                    }
                )
        results.sort(key=lambda x: x["last_active_at"], reverse=True)
        return results[: min(limit, 20)]
