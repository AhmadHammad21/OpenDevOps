"""SQLite backend — zero-config local persistence, ideal for single-server deployments."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from loguru import logger

from agent.db.base import DatabaseBackend
from config import settings


_DDL = """
CREATE TABLE IF NOT EXISTS sessions (
    id             TEXT PRIMARY KEY,
    title          TEXT,
    model          TEXT NOT NULL DEFAULT '',
    aws_region     TEXT NOT NULL DEFAULT 'us-east-1',
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    last_active_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    is_deleted     INTEGER NOT NULL DEFAULT 0,
    deleted_at     TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id         TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    metadata   TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    message_id  TEXT REFERENCES messages(id),
    tool_name   TEXT NOT NULL,
    args        TEXT NOT NULL DEFAULT '{}',
    result      TEXT NOT NULL DEFAULT '{}',
    error       TEXT,
    duration_ms INTEGER,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);

CREATE TABLE IF NOT EXISTS usage_events (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    message_id      TEXT REFERENCES messages(id),
    model           TEXT NOT NULL,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    cost_usd        REAL,
    latency_ms      INTEGER NOT NULL DEFAULT 0,
    tool_call_count INTEGER NOT NULL DEFAULT 0,
    metadata        TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);
"""

_SERVICE_MAP: dict[str, str] = {
    "get_alarms": "CloudWatch", "get_alarm_history": "CloudWatch",
    "get_metric_data": "CloudWatch", "get_log_events": "CloudWatch",
    "describe_log_groups": "CloudWatch", "query_logs_insights": "CloudWatch",
    "lookup_cloudtrail_events": "CloudTrail",
    "list_ecs_clusters": "ECS", "list_ecs_services": "ECS",
    "describe_ecs_service": "ECS", "get_ecs_task_logs": "ECS",
    "list_lambda_functions": "Lambda", "get_lambda_function_config": "Lambda",
    "get_lambda_error_rate": "Lambda",
    "describe_ec2_instances": "EC2", "get_ec2_system_status": "EC2",
    "describe_rds_instances": "RDS", "get_rds_events": "RDS",
    "get_caller_identity": "IAM", "get_iam_role_policies": "IAM",
    "submit_investigation": "Agent",
}


class SQLiteBackend(DatabaseBackend):
    """aiosqlite-backed persistent storage with LangGraph SQLite checkpointer."""

    def __init__(self) -> None:
        self._path: str = settings.sqlite_path
        self._conn: Any = None
        self._checkpointer: Any = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def init(self) -> Any:
        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        os.makedirs(os.path.dirname(os.path.abspath(self._path)), exist_ok=True)

        self._conn = await aiosqlite.connect(self._path)
        # WAL mode: concurrent reads don't block writes on a single-server deployment
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")

        for stmt in _DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                await self._conn.execute(stmt)
        await self._conn.commit()

        # Migrate existing databases: add metadata column if absent
        try:
            await self._conn.execute(
                "ALTER TABLE usage_events ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'"
            )
            await self._conn.commit()
        except Exception:
            pass  # column already exists

        # LangGraph checkpointer uses its own connection to the same file
        cp_conn = await aiosqlite.connect(self._path)
        self._checkpointer = AsyncSqliteSaver(cp_conn)
        await self._checkpointer.setup()

        logger.info("SQLite backend ready — path={}", self._path)
        return self._checkpointer

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            logger.info("SQLite connection closed")

    @property
    def checkpointer(self) -> Any:
        return self._checkpointer

    # ── Low-level helpers ─────────────────────────────────────────────────────

    async def _exec(self, sql: str, *params: Any) -> None:
        if self._conn is None:
            return
        try:
            await self._conn.execute(sql, params)
            await self._conn.commit()
        except Exception as e:
            logger.error("SQLite write failed: {}", e)

    async def _fetchall(self, sql: str, *params: Any) -> list[dict]:
        if self._conn is None:
            return []
        try:
            async with self._conn.execute(sql, params) as cur:
                rows = await cur.fetchall()
                if not rows:
                    return []
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, r)) for r in rows]
        except Exception as e:
            logger.error("SQLite read failed: {}", e)
            return []

    async def _fetchone(self, sql: str, *params: Any) -> dict | None:
        if self._conn is None:
            return None
        try:
            async with self._conn.execute(sql, params) as cur:
                row = await cur.fetchone()
                if row is None:
                    return None
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))
        except Exception as e:
            logger.error("SQLite read failed: {}", e)
            return None

    # ── App helpers ───────────────────────────────────────────────────────────

    async def upsert_session(
        self,
        session_id: str,
        model: str,
        aws_region: str,
        title: str | None = None,
    ) -> None:
        await self._exec(
            """
            INSERT INTO sessions (id, title, model, aws_region)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                last_active_at = strftime('%Y-%m-%dT%H:%M:%S', 'now'),
                model = excluded.model
            """,
            session_id, title, model, aws_region,
        )

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> str:
        msg_id = str(uuid.uuid4())
        await self._exec(
            "INSERT INTO messages (id, session_id, role, content, metadata) VALUES (?, ?, ?, ?, ?)",
            msg_id, session_id, role, content, json.dumps(metadata or {}),
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
        await self._exec(
            """
            INSERT INTO tool_calls
                (id, session_id, message_id, tool_name, args, result, error, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            str(uuid.uuid4()), session_id, message_id, tool_name,
            json.dumps(args), json.dumps(result), error, duration_ms,
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
        await self._exec(
            """
            INSERT INTO usage_events
                (id, session_id, message_id, model, input_tokens, output_tokens,
                 cost_usd, latency_ms, tool_call_count, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            str(uuid.uuid4()), session_id, message_id, model,
            input_tokens, output_tokens, cost_usd, latency_ms, tool_call_count,
            json.dumps(metadata or {}),
        )

    async def list_sessions(self) -> list[dict]:
        rows = await self._fetchall(
            "SELECT id, title, last_active_at, model, aws_region FROM sessions WHERE is_deleted = 0 ORDER BY last_active_at DESC"
        )
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "last_active_at": r["last_active_at"],
                "model": r["model"],
                "aws_region": r["aws_region"],
            }
            for r in rows
        ]

    async def get_messages(self, session_id: str) -> list[dict]:
        session = await self._fetchone(
            "SELECT is_deleted FROM sessions WHERE id = ?", session_id
        )
        if session is None or session.get("is_deleted"):
            return []

        messages = await self._fetchall(
            "SELECT id, role, content, created_at FROM messages WHERE session_id = ? ORDER BY created_at ASC",
            session_id,
        )
        tool_calls = await self._fetchall(
            "SELECT message_id, tool_name, args, result, error FROM tool_calls WHERE session_id = ? ORDER BY created_at ASC",
            session_id,
        )
        usage_rows = await self._fetchall(
            "SELECT message_id, model, input_tokens, output_tokens, cost_usd, latency_ms FROM usage_events WHERE session_id = ?",
            session_id,
        )

        tc_by_msg: dict[str, list] = {}
        for tc in tool_calls:
            mid = tc["message_id"]
            if mid:
                tc_by_msg.setdefault(mid, []).append({
                    "tool_name": tc["tool_name"],
                    "args": json.loads(tc["args"]) if isinstance(tc["args"], str) else tc["args"],
                    "result": json.loads(tc["result"]) if isinstance(tc["result"], str) else tc["result"],
                    "error": tc["error"],
                })

        usage_by_msg = {
            u["message_id"]: {
                "model": u["model"],
                "input_tokens": u["input_tokens"],
                "output_tokens": u["output_tokens"],
                "cost_usd": float(u["cost_usd"]) if u["cost_usd"] is not None else None,
                "latency_ms": u["latency_ms"],
            }
            for u in usage_rows
            if u["message_id"]
        }

        result = []
        for msg in messages:
            mid = msg["id"]
            item: dict = {
                "id": mid,
                "role": msg["role"],
                "content": msg["content"],
                "created_at": msg["created_at"],
                "tool_calls": [],
                "usage": None,
            }
            if msg["role"] == "assistant":
                item["tool_calls"] = tc_by_msg.get(mid, [])
                item["usage"] = usage_by_msg.get(mid)
            result.append(item)
        return result

    async def delete_session(self, session_id: str) -> None:
        await self._exec(
            "UPDATE sessions SET is_deleted = 1, deleted_at = strftime('%Y-%m-%dT%H:%M:%S', 'now') WHERE id = ?",
            session_id,
        )

    # ── Analytics ─────────────────────────────────────────────────────────────

    async def get_dashboard_stats(self) -> dict:
        summary = await self._fetchone("""
            SELECT
                (SELECT COUNT(*) FROM sessions WHERE is_deleted = 0) AS total_sessions,
                (SELECT COUNT(*) FROM messages m
                    JOIN sessions s ON s.id = m.session_id
                    WHERE s.is_deleted = 0 AND m.role = 'user') AS total_queries,
                (SELECT COUNT(*) FROM tool_calls tc
                    JOIN sessions s ON s.id = tc.session_id
                    WHERE s.is_deleted = 0) AS total_tool_calls,
                (SELECT COUNT(*) FROM tool_calls tc
                    JOIN sessions s ON s.id = tc.session_id
                    WHERE s.is_deleted = 0 AND tc.error IS NOT NULL) AS total_tool_errors,
                (SELECT COALESCE(SUM(input_tokens), 0) FROM usage_events ue
                    JOIN sessions s ON s.id = ue.session_id
                    WHERE s.is_deleted = 0) AS total_input_tokens,
                (SELECT COALESCE(SUM(output_tokens), 0) FROM usage_events ue
                    JOIN sessions s ON s.id = ue.session_id
                    WHERE s.is_deleted = 0) AS total_output_tokens,
                (SELECT COALESCE(SUM(cost_usd), 0) FROM usage_events ue
                    JOIN sessions s ON s.id = ue.session_id
                    WHERE s.is_deleted = 0) AS total_cost_usd,
                (SELECT COALESCE(AVG(latency_ms), 0) FROM usage_events ue
                    JOIN sessions s ON s.id = ue.session_id
                    WHERE s.is_deleted = 0) AS avg_latency_ms
        """) or {}

        activity_rows = await self._fetchall("""
            SELECT strftime('%Y-%m-%d', last_active_at) AS day, COUNT(*) AS sessions
            FROM sessions
            WHERE is_deleted = 0
              AND last_active_at > datetime('now', '-14 days')
            GROUP BY 1 ORDER BY 1
        """)

        tool_rows = await self._fetchall("""
            SELECT
                tc.tool_name,
                COUNT(*) AS call_count,
                SUM(CASE WHEN tc.error IS NOT NULL THEN 1 ELSE 0 END) AS error_count
            FROM tool_calls tc
            JOIN sessions s ON s.id = tc.session_id
            WHERE s.is_deleted = 0
            GROUP BY tc.tool_name
            ORDER BY call_count DESC
            LIMIT 12
        """)
        top_tools = [
            {"tool": r["tool_name"], "count": int(r["call_count"]), "errors": int(r["error_count"])}
            for r in tool_rows
        ]

        service_totals: dict[str, int] = {}
        for t in top_tools:
            svc = _SERVICE_MAP.get(t["tool"], "Other")
            service_totals[svc] = service_totals.get(svc, 0) + t["count"]
        total_calls = sum(service_totals.values()) or 1
        service_breakdown = sorted(
            [
                {"service": svc, "calls": cnt, "pct": round(cnt / total_calls * 100, 1)}
                for svc, cnt in service_totals.items()
            ],
            key=lambda x: x["calls"],
            reverse=True,
        )

        recent_rows = await self._fetchall("""
            SELECT
                s.id, s.title, s.last_active_at, s.model,
                COUNT(DISTINCT CASE WHEN m.role = 'user' THEN m.id END) AS query_count,
                COUNT(DISTINCT tc.id)                                    AS tool_count,
                COALESCE(SUM(ue.cost_usd), 0)                           AS cost_usd
            FROM sessions s
            LEFT JOIN messages     m  ON m.session_id  = s.id
            LEFT JOIN tool_calls   tc ON tc.session_id = s.id
            LEFT JOIN usage_events ue ON ue.session_id = s.id
            WHERE s.is_deleted = 0
            GROUP BY s.id, s.title, s.last_active_at, s.model
            ORDER BY s.last_active_at DESC
            LIMIT 6
        """)
        recent_sessions = [
            {
                "id": r["id"],
                "title": r["title"],
                "last_active_at": r["last_active_at"],
                "model": r["model"],
                "query_count": int(r["query_count"] or 0),
                "tool_count": int(r["tool_count"] or 0),
                "cost_usd": float(r["cost_usd"] or 0),
            }
            for r in recent_rows
        ]

        rc_rows = await self._fetchall("""
            SELECT
                json_extract(tc.args, '$.root_cause_category') AS category,
                COUNT(*) AS count
            FROM tool_calls tc
            JOIN sessions s ON s.id = tc.session_id
            WHERE s.is_deleted = 0
              AND tc.tool_name = 'submit_investigation'
              AND json_extract(tc.args, '$.root_cause_category') IS NOT NULL
            GROUP BY 1 ORDER BY 2 DESC
        """)

        return {
            "summary": {
                "total_sessions":    int(summary.get("total_sessions", 0) or 0),
                "total_queries":     int(summary.get("total_queries", 0) or 0),
                "total_tool_calls":  int(summary.get("total_tool_calls", 0) or 0),
                "total_tool_errors": int(summary.get("total_tool_errors", 0) or 0),
                "total_input_tokens":  int(summary.get("total_input_tokens", 0) or 0),
                "total_output_tokens": int(summary.get("total_output_tokens", 0) or 0),
                "total_cost_usd":    float(summary.get("total_cost_usd", 0) or 0),
                "avg_latency_ms":    round(float(summary.get("avg_latency_ms", 0) or 0)),
            },
            "activity": [
                {"date": r["day"], "sessions": int(r["sessions"])}
                for r in activity_rows
            ],
            "top_tools": top_tools,
            "service_breakdown": service_breakdown,
            "recent_sessions": recent_sessions,
            "root_causes": [
                {"category": r["category"], "count": int(r["count"])}
                for r in rc_rows
            ],
        }

    async def get_history_stats(self, days: int = 30) -> dict:
        cutoff = f"-{days} days"

        alarm_rows = await self._fetchall("""
            SELECT
                json_extract(tc.args, '$.alarm_name') AS alarm_name,
                COUNT(DISTINCT tc.session_id)          AS session_count,
                COUNT(*)                               AS total_lookups,
                MAX(s.last_active_at)                  AS last_seen
            FROM tool_calls tc
            JOIN sessions s ON s.id = tc.session_id
            WHERE s.is_deleted = 0
              AND tc.tool_name = 'get_alarm_history'
              AND json_extract(tc.args, '$.alarm_name') IS NOT NULL
              AND s.last_active_at > datetime('now', ?)
            GROUP BY 1
            ORDER BY session_count DESC, total_lookups DESC
            LIMIT 10
        """, cutoff)

        lambda_rows = await self._fetchall("""
            SELECT
                json_extract(tc.args, '$.function_name') AS function_name,
                COUNT(DISTINCT tc.session_id)             AS session_count,
                COUNT(*)                                  AS total_calls,
                MAX(s.last_active_at)                     AS last_seen
            FROM tool_calls tc
            JOIN sessions s ON s.id = tc.session_id
            WHERE s.is_deleted = 0
              AND tc.tool_name IN ('get_lambda_error_rate', 'get_lambda_function_config')
              AND json_extract(tc.args, '$.function_name') IS NOT NULL
              AND s.last_active_at > datetime('now', ?)
            GROUP BY 1 ORDER BY session_count DESC
            LIMIT 10
        """, cutoff)

        error_rows = await self._fetchall("""
            SELECT
                tc.tool_name,
                substr(tc.error, 1, 120) AS error_snippet,
                COUNT(*)                 AS count,
                MAX(tc.created_at)       AS last_seen
            FROM tool_calls tc
            JOIN sessions s ON s.id = tc.session_id
            WHERE s.is_deleted = 0
              AND tc.error IS NOT NULL
              AND s.last_active_at > datetime('now', ?)
            GROUP BY 1, 2 ORDER BY count DESC
            LIMIT 10
        """, cutoff)

        trend_rows = await self._fetchall("""
            SELECT
                strftime('%Y-%m-%d', last_active_at) AS day,
                COUNT(*) AS count
            FROM sessions
            WHERE is_deleted = 0
              AND last_active_at > datetime('now', ?)
            GROUP BY 1 ORDER BY 1
        """, cutoff)

        return {
            "days": days,
            "top_alarms": [
                {
                    "alarm_name":    r["alarm_name"],
                    "session_count": int(r["session_count"]),
                    "total_lookups": int(r["total_lookups"]),
                    "last_seen":     r["last_seen"],
                }
                for r in alarm_rows
            ],
            "top_lambdas": [
                {
                    "function_name": r["function_name"],
                    "session_count": int(r["session_count"]),
                    "total_calls":   int(r["total_calls"]),
                    "last_seen":     r["last_seen"],
                }
                for r in lambda_rows
            ],
            "recurring_errors": [
                {
                    "tool_name":     r["tool_name"],
                    "error_snippet": r["error_snippet"],
                    "count":         int(r["count"]),
                    "last_seen":     r["last_seen"],
                }
                for r in error_rows
            ],
            "trend": [
                {"date": r["day"], "count": int(r["count"])}
                for r in trend_rows
            ],
        }

    async def search_sessions(self, query: str, limit: int = 10) -> list[dict]:
        if not query.strip():
            return []
        pattern = f"%{query}%"
        rows = await self._fetchall("""
            SELECT id, title, last_active_at, model, snippet
            FROM (
                SELECT
                    s.id, s.title, s.last_active_at, s.model,
                    substr(m.content, 1, 200) AS snippet,
                    ROW_NUMBER() OVER (PARTITION BY s.id ORDER BY m.created_at ASC) AS rn
                FROM sessions s
                JOIN messages m ON m.session_id = s.id AND m.role = 'user'
                WHERE s.is_deleted = 0
                  AND (s.title LIKE ? OR m.content LIKE ?)
            ) sub
            WHERE rn = 1
            ORDER BY last_active_at DESC
            LIMIT ?
        """, pattern, pattern, min(limit, 20))
        return [
            {
                "id":             r["id"],
                "title":          r["title"],
                "last_active_at": r["last_active_at"],
                "model":          r["model"],
                "snippet":        r["snippet"],
            }
            for r in rows
        ]
