"""PostgreSQL backend — full persistence, recommended for production."""

from __future__ import annotations

import uuid
from typing import Any

from loguru import logger

from opendevops_core.agent.db.base import DatabaseBackend
from opendevops_core.config import settings


class PostgresBackend(DatabaseBackend):
    """Async PostgreSQL connection pool, LangGraph checkpointer, and all write helpers."""

    def __init__(self) -> None:
        self._pool: Any = None
        self._checkpointer: Any = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def init(self) -> Any:
        if not settings.database_url:
            logger.warning("DATABASE_URL not set — falling back to MemorySaver")
            return self._use_memory()

        try:
            import psycopg  # type: ignore
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg_pool import AsyncConnectionPool

            self._pool = AsyncConnectionPool(
                conninfo=settings.database_url,
                open=False,
                kwargs={"prepare_threshold": None},
            )
            await self._pool.open()
            self._checkpointer = AsyncPostgresSaver(self._pool)

            setup_conn = await psycopg.AsyncConnection.connect(
                settings.database_url, autocommit=True
            )
            try:
                await AsyncPostgresSaver(setup_conn).setup()
            finally:
                await setup_conn.close()

            logger.info("PostgreSQL connected — checkpointer ready")
            return self._checkpointer

        except Exception as e:
            logger.error("PostgreSQL init failed ({}) — falling back to MemorySaver", e)
            return self._use_memory()

    def _use_memory(self) -> Any:
        from langgraph.checkpoint.memory import MemorySaver

        self._checkpointer = MemorySaver()
        return self._checkpointer

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            logger.info("PostgreSQL connection pool closed")

    @property
    def checkpointer(self) -> Any:
        return self._checkpointer

    # ── Low-level helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _jsonb(value: Any) -> Any:
        from psycopg.types.json import Jsonb  # type: ignore

        return Jsonb(value)

    async def _exec(self, query: str, *params: Any) -> None:
        if self._pool is None:
            return
        try:
            async with self._pool.connection() as conn:
                await conn.execute(query, params)
        except Exception as e:
            logger.error("DB write failed: {}", e)

    async def _fetchall(self, query: str, *params: Any) -> list[dict]:
        if self._pool is None:
            return []
        try:
            async with self._pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    rows = await cur.fetchall()
                    if not rows:
                        return []
                    cols = [desc[0] for desc in cur.description]
                    return [dict(zip(cols, row)) for row in rows]
        except Exception as e:
            logger.error("DB read failed: {}", e)
            return []

    async def _fetchrow(self, query: str, *params: Any) -> dict | None:
        if self._pool is None:
            return None
        try:
            async with self._pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    row = await cur.fetchone()
                    if row is None:
                        return None
                    cols = [desc[0] for desc in cur.description]
                    return dict(zip(cols, row))
        except Exception as e:
            logger.error("DB read failed: {}", e)
            return None

    # ── App helpers ───────────────────────────────────────────────────────────

    async def upsert_session(
        self,
        session_id: str,
        model: str,
        aws_region: str,
        title: str | None = None,
        source: str = "chat",
    ) -> None:
        await self._exec(
            """
            INSERT INTO sessions (id, title, model, aws_region, source)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                last_active_at = NOW(),
                model = EXCLUDED.model,
                user_interacted = CASE
                    WHEN EXCLUDED.source = 'chat' THEN TRUE
                    ELSE sessions.user_interacted
                END
            """,
            uuid.UUID(session_id),
            title,
            model,
            aws_region,
            source,
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
            "INSERT INTO messages (id, session_id, role, content, metadata) VALUES (%s, %s, %s, %s, %s)",
            uuid.UUID(msg_id),
            uuid.UUID(session_id),
            role,
            content,
            self._jsonb(metadata or {}),
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
                (session_id, message_id, tool_name, args, result, error, duration_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            uuid.UUID(session_id),
            uuid.UUID(message_id) if message_id else None,
            tool_name,
            self._jsonb(args),
            self._jsonb(result),
            error,
            duration_ms,
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
                (session_id, message_id, model, input_tokens, output_tokens,
                 cost_usd, latency_ms, tool_call_count, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            uuid.UUID(session_id),
            uuid.UUID(message_id) if message_id else None,
            model,
            input_tokens,
            output_tokens,
            cost_usd,
            latency_ms,
            tool_call_count,
            self._jsonb(metadata or {}),
        )

    async def list_sessions(self, limit: int = 15, offset: int = 0) -> list[dict]:
        rows = await self._fetchall(
            "SELECT id, title, last_active_at, model, aws_region FROM sessions"
            " WHERE is_deleted = FALSE AND (source = 'chat' OR user_interacted = TRUE)"
            " ORDER BY last_active_at DESC LIMIT %s OFFSET %s",
            limit,
            offset,
        )
        return [
            {
                "id": str(r["id"]),
                "title": r["title"],
                "last_active_at": r["last_active_at"].isoformat() if r["last_active_at"] else None,
                "model": r["model"],
                "aws_region": r["aws_region"],
            }
            for r in rows
        ]

    async def get_messages(self, session_id: str) -> list[dict]:
        uid = uuid.UUID(session_id)
        session = await self._fetchrow("SELECT is_deleted FROM sessions WHERE id = %s", uid)
        if session is None or session.get("is_deleted"):
            return []

        messages = await self._fetchall(
            "SELECT id, role, content, created_at FROM messages WHERE session_id = %s ORDER BY created_at ASC",
            uid,
        )
        tool_calls = await self._fetchall(
            "SELECT message_id, tool_name, args, result, error FROM tool_calls WHERE session_id = %s ORDER BY created_at ASC",
            uid,
        )
        usage_rows = await self._fetchall(
            "SELECT message_id, model, input_tokens, output_tokens, cost_usd, latency_ms FROM usage_events WHERE session_id = %s",
            uid,
        )

        tc_by_msg: dict[str, list] = {}
        for tc in tool_calls:
            mid = str(tc["message_id"])
            tc_by_msg.setdefault(mid, []).append(
                {
                    "tool_name": tc["tool_name"],
                    "args": tc["args"],
                    "result": tc["result"],
                    "error": tc["error"],
                }
            )

        usage_by_msg = {
            str(u["message_id"]): {
                "model": u["model"],
                "input_tokens": u["input_tokens"],
                "output_tokens": u["output_tokens"],
                "cost_usd": float(u["cost_usd"]) if u["cost_usd"] is not None else None,
                "latency_ms": u["latency_ms"],
            }
            for u in usage_rows
        }

        result = []
        for msg in messages:
            mid = str(msg["id"])
            item: dict = {
                "id": mid,
                "role": msg["role"],
                "content": msg["content"],
                "created_at": msg["created_at"].isoformat() if msg["created_at"] else None,
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
            "UPDATE sessions SET is_deleted = TRUE, deleted_at = NOW() WHERE id = %s",
            uuid.UUID(session_id),
        )

    async def rename_session(self, session_id: str, title: str) -> None:
        await self._exec(
            "UPDATE sessions SET title = %s WHERE id = %s AND is_deleted = FALSE",
            title,
            uuid.UUID(session_id),
        )

    # ── Analytics ─────────────────────────────────────────────────────────────

    async def get_dashboard_stats(self) -> dict:
        _SERVICE_MAP: dict[str, str] = {
            "get_alarms": "CloudWatch",
            "get_alarm_history": "CloudWatch",
            "get_metric_data": "CloudWatch",
            "get_log_events": "CloudWatch",
            "describe_log_groups": "CloudWatch",
            "query_logs_insights": "CloudWatch",
            "lookup_cloudtrail_events": "CloudTrail",
            "list_ecs_clusters": "ECS",
            "list_ecs_services": "ECS",
            "describe_ecs_service": "ECS",
            "get_ecs_task_logs": "ECS",
            "list_lambda_functions": "Lambda",
            "get_lambda_function_config": "Lambda",
            "get_lambda_error_rate": "Lambda",
            "describe_ec2_instances": "EC2",
            "get_ec2_system_status": "EC2",
            "describe_rds_instances": "RDS",
            "get_rds_events": "RDS",
            "get_caller_identity": "IAM",
            "get_iam_role_policies": "IAM",
            "submit_investigation": "Agent",
        }

        summary_row = await self._fetchrow("""
            SELECT
                (SELECT COUNT(*) FROM sessions WHERE is_deleted = FALSE) AS total_sessions,
                (SELECT COUNT(*) FROM messages m JOIN sessions s ON s.id = m.session_id WHERE s.is_deleted = FALSE AND m.role = 'user') AS total_queries,
                (SELECT COUNT(*) FROM tool_calls tc JOIN sessions s ON s.id = tc.session_id WHERE s.is_deleted = FALSE) AS total_tool_calls,
                (SELECT COUNT(*) FROM tool_calls tc JOIN sessions s ON s.id = tc.session_id WHERE s.is_deleted = FALSE AND tc.error IS NOT NULL) AS total_tool_errors,
                (SELECT COALESCE(SUM(input_tokens), 0) FROM usage_events ue JOIN sessions s ON s.id = ue.session_id WHERE s.is_deleted = FALSE) AS total_input_tokens,
                (SELECT COALESCE(SUM(output_tokens), 0) FROM usage_events ue JOIN sessions s ON s.id = ue.session_id WHERE s.is_deleted = FALSE) AS total_output_tokens,
                (SELECT COALESCE(SUM(cost_usd), 0) FROM usage_events ue JOIN sessions s ON s.id = ue.session_id WHERE s.is_deleted = FALSE) AS total_cost_usd,
                (SELECT COALESCE(AVG(latency_ms), 0) FROM usage_events ue JOIN sessions s ON s.id = ue.session_id WHERE s.is_deleted = FALSE) AS avg_latency_ms,
                (SELECT COUNT(*) FROM usage_events ue JOIN sessions s ON s.id = ue.session_id
                    WHERE s.is_deleted = FALSE AND ue.metadata @> '{"summarization": true}'::jsonb) AS total_summarizations,
                (SELECT COALESCE(SUM((ue.metadata->>'chars_removed')::int), 0) FROM usage_events ue JOIN sessions s ON s.id = ue.session_id
                    WHERE s.is_deleted = FALSE AND ue.metadata @> '{"summarization": true}'::jsonb) AS total_chars_compacted
        """)
        summary = summary_row or {}

        activity_rows = await self._fetchall("""
            SELECT DATE_TRUNC('day', last_active_at AT TIME ZONE 'UTC')::date AS day, COUNT(*) AS sessions
            FROM sessions WHERE is_deleted = FALSE AND last_active_at > NOW() - INTERVAL '14 days'
            GROUP BY 1 ORDER BY 1
        """)

        tool_rows = await self._fetchall("""
            SELECT tc.tool_name, COUNT(*) AS call_count,
                   COUNT(*) FILTER (WHERE tc.error IS NOT NULL) AS error_count
            FROM tool_calls tc JOIN sessions s ON s.id = tc.session_id
            WHERE s.is_deleted = FALSE
            GROUP BY tc.tool_name ORDER BY call_count DESC LIMIT 12
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
                {"service": s, "calls": c, "pct": round(c / total_calls * 100, 1)}
                for s, c in service_totals.items()
            ],
            key=lambda x: x["calls"],
            reverse=True,
        )

        recent_rows = await self._fetchall("""
            SELECT s.id, s.title, s.last_active_at, s.model,
                   COUNT(DISTINCT m.id) FILTER (WHERE m.role = 'user') AS query_count,
                   COUNT(DISTINCT tc.id) AS tool_count,
                   COALESCE(SUM(ue.cost_usd), 0) AS cost_usd
            FROM sessions s
            LEFT JOIN messages     m  ON m.session_id  = s.id
            LEFT JOIN tool_calls   tc ON tc.session_id = s.id
            LEFT JOIN usage_events ue ON ue.session_id = s.id
            WHERE s.is_deleted = FALSE
            GROUP BY s.id, s.title, s.last_active_at, s.model
            ORDER BY s.last_active_at DESC LIMIT 6
        """)
        recent_sessions = [
            {
                "id": str(r["id"]),
                "title": r["title"],
                "last_active_at": r["last_active_at"].isoformat() if r["last_active_at"] else None,
                "model": r["model"],
                "query_count": int(r["query_count"] or 0),
                "tool_count": int(r["tool_count"] or 0),
                "cost_usd": float(r["cost_usd"] or 0),
            }
            for r in recent_rows
        ]

        rc_rows = await self._fetchall("""
            SELECT tc.args->>'root_cause_category' AS category, COUNT(*) AS count
            FROM tool_calls tc JOIN sessions s ON s.id = tc.session_id
            WHERE s.is_deleted = FALSE AND tc.tool_name = 'submit_investigation'
              AND tc.args->>'root_cause_category' IS NOT NULL
            GROUP BY 1 ORDER BY 2 DESC
        """)

        return {
            "summary": {
                "total_sessions": int(summary.get("total_sessions", 0) or 0),
                "total_queries": int(summary.get("total_queries", 0) or 0),
                "total_tool_calls": int(summary.get("total_tool_calls", 0) or 0),
                "total_tool_errors": int(summary.get("total_tool_errors", 0) or 0),
                "total_input_tokens": int(summary.get("total_input_tokens", 0) or 0),
                "total_output_tokens": int(summary.get("total_output_tokens", 0) or 0),
                "total_cost_usd": float(summary.get("total_cost_usd", 0) or 0),
                "avg_latency_ms": round(float(summary.get("avg_latency_ms", 0) or 0)),
                "total_summarizations": int(summary.get("total_summarizations", 0) or 0),
                "total_chars_compacted": int(summary.get("total_chars_compacted", 0) or 0),
            },
            "activity": [
                {"date": str(r["day"]), "sessions": int(r["sessions"])} for r in activity_rows
            ],
            "top_tools": top_tools,
            "service_breakdown": service_breakdown,
            "recent_sessions": recent_sessions,
            "root_causes": [{"category": r["category"], "count": int(r["count"])} for r in rc_rows],
        }

    async def get_history_stats(self, days: int = 30) -> dict:
        alarm_rows = await self._fetchall(
            """
            SELECT tc.args->>'alarm_name' AS alarm_name,
                   COUNT(DISTINCT tc.session_id) AS session_count,
                   COUNT(*) AS total_lookups, MAX(s.last_active_at) AS last_seen
            FROM tool_calls tc JOIN sessions s ON s.id = tc.session_id
            WHERE s.is_deleted = FALSE AND tc.tool_name = 'get_alarm_history'
              AND tc.args->>'alarm_name' IS NOT NULL
              AND s.last_active_at > NOW() - (%s * INTERVAL '1 day')
            GROUP BY 1 ORDER BY session_count DESC, total_lookups DESC LIMIT 10
        """,
            days,
        )

        lambda_rows = await self._fetchall(
            """
            SELECT tc.args->>'function_name' AS function_name,
                   COUNT(DISTINCT tc.session_id) AS session_count,
                   COUNT(*) AS total_calls, MAX(s.last_active_at) AS last_seen
            FROM tool_calls tc JOIN sessions s ON s.id = tc.session_id
            WHERE s.is_deleted = FALSE
              AND tc.tool_name IN ('get_lambda_error_rate', 'get_lambda_function_config')
              AND tc.args->>'function_name' IS NOT NULL
              AND s.last_active_at > NOW() - (%s * INTERVAL '1 day')
            GROUP BY 1 ORDER BY session_count DESC LIMIT 10
        """,
            days,
        )

        error_rows = await self._fetchall(
            """
            SELECT tc.tool_name, LEFT(tc.error, 120) AS error_snippet,
                   COUNT(*) AS count, MAX(tc.created_at) AS last_seen
            FROM tool_calls tc JOIN sessions s ON s.id = tc.session_id
            WHERE s.is_deleted = FALSE AND tc.error IS NOT NULL
              AND s.last_active_at > NOW() - (%s * INTERVAL '1 day')
            GROUP BY 1, 2 ORDER BY count DESC LIMIT 10
        """,
            days,
        )

        trend_rows = await self._fetchall(
            """
            SELECT DATE_TRUNC('day', last_active_at AT TIME ZONE 'UTC')::date AS day,
                   COUNT(*) AS count
            FROM sessions WHERE is_deleted = FALSE
              AND last_active_at > NOW() - (%s * INTERVAL '1 day')
            GROUP BY 1 ORDER BY 1
        """,
            days,
        )

        return {
            "days": days,
            "top_alarms": [
                {
                    "alarm_name": r["alarm_name"],
                    "session_count": int(r["session_count"]),
                    "total_lookups": int(r["total_lookups"]),
                    "last_seen": r["last_seen"].isoformat() if r["last_seen"] else None,
                }
                for r in alarm_rows
            ],
            "top_lambdas": [
                {
                    "function_name": r["function_name"],
                    "session_count": int(r["session_count"]),
                    "total_calls": int(r["total_calls"]),
                    "last_seen": r["last_seen"].isoformat() if r["last_seen"] else None,
                }
                for r in lambda_rows
            ],
            "recurring_errors": [
                {
                    "tool_name": r["tool_name"],
                    "error_snippet": r["error_snippet"],
                    "count": int(r["count"]),
                    "last_seen": r["last_seen"].isoformat() if r["last_seen"] else None,
                }
                for r in error_rows
            ],
            "trend": [{"date": str(r["day"]), "count": int(r["count"])} for r in trend_rows],
        }

    # ── User / auth ───────────────────────────────────────────────────────────

    async def count_users(self) -> int:
        row = await self._fetchrow(
            "SELECT COUNT(*) AS n FROM users WHERE password_hash IS NOT NULL"
        )
        return int(row["n"]) if row else 0

    async def get_user_by_email(self, email: str) -> dict | None:
        return await self._fetchrow("SELECT * FROM users WHERE email = %s", email)

    async def get_user_by_id(self, user_id: str) -> dict | None:
        return await self._fetchrow("SELECT * FROM users WHERE id = %s", uuid.UUID(user_id))

    async def create_org(self, name: str, slug: str) -> dict | None:
        row = await self._fetchrow(
            """
            INSERT INTO organizations (name, slug)
            VALUES (%s, %s)
            ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
            RETURNING id, name, slug
            """,
            name,
            slug,
        )
        if row:
            row["id"] = str(row["id"])
        return row

    async def get_first_org(self) -> dict | None:
        row = await self._fetchrow(
            "SELECT id, name, slug FROM organizations ORDER BY created_at ASC LIMIT 1"
        )
        if row:
            row["id"] = str(row["id"])
        return row

    async def create_user(
        self,
        email: str,
        name: str,
        password_hash: str,
        role: str,
        org_id: str | None = None,
    ) -> dict | None:
        if org_id:
            row = await self._fetchrow(
                """
                INSERT INTO users (email, name, password_hash, role, org_id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, email, name, role, created_at
                """,
                email,
                name,
                password_hash,
                role,
                uuid.UUID(org_id),
            )
        else:
            row = await self._fetchrow(
                """
                INSERT INTO users (email, name, password_hash, role)
                VALUES (%s, %s, %s, %s)
                RETURNING id, email, name, role, created_at
                """,
                email,
                name,
                password_hash,
                role,
            )
        if row:
            row["id"] = str(row["id"])
        return row

    async def list_users(self) -> list[dict]:
        rows = await self._fetchall(
            "SELECT id, email, name, role, created_at FROM users ORDER BY created_at ASC"
        )
        return [
            {
                "id": str(r["id"]),
                "email": r["email"],
                "name": r["name"],
                "role": r["role"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    async def update_user(self, user_id: str, **fields: Any) -> dict | None:
        sets = ", ".join(f"{k} = %s" for k in fields)
        values = [*fields.values(), uuid.UUID(user_id)]
        row = await self._fetchrow(
            f"UPDATE users SET {sets}, updated_at = NOW() WHERE id = %s"
            " RETURNING id, email, name, role, created_at",
            *values,
        )
        if row:
            row["id"] = str(row["id"])
        return row

    async def assign_org_to_users_without_org(self, org_id: str) -> None:
        await self._exec(
            "UPDATE users SET org_id = %s WHERE org_id IS NULL",
            uuid.UUID(org_id),
        )

    async def delete_user(self, user_id: str) -> None:
        await self._exec("DELETE FROM users WHERE id = %s", uuid.UUID(user_id))

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
        evidence: list | None = None,
    ) -> str:
        import json as _json

        row = await self._fetchrow(
            "INSERT INTO alerts"
            " (service, error, resolution, confidence, sns_sent, dedup_key, status,"
            "  session_id, trigger_source, evidence)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            service,
            error,
            resolution,
            confidence,
            sns_sent,
            dedup_key,
            status,
            uuid.UUID(session_id) if session_id else None,
            trigger_source,
            _json.dumps(evidence or []),
        )
        return str(row["id"]) if row else ""

    async def add_notification(
        self,
        alert_id: str,
        channel: str,
        status: str = "attempted",
        error: str | None = None,
    ) -> None:
        await self._exec(
            "INSERT INTO alert_notifications (alert_id, channel, status, error)"
            " VALUES (%s, %s, %s, %s)",
            uuid.UUID(alert_id),
            channel,
            status,
            error,
        )

    async def is_recent_alert(self, dedup_key: str, within_minutes: int = 3) -> bool:
        row = await self._fetchrow(
            "SELECT 1 FROM alerts WHERE dedup_key = %s"
            " AND created_at > NOW() - (%s * INTERVAL '1 minute') LIMIT 1",
            dedup_key,
            within_minutes,
        )
        return row is not None

    async def claim_incident(
        self,
        incident_key: str,
        trigger_source: str,
        within_minutes: int = 3,
    ) -> bool:
        row = await self._fetchrow(
            "INSERT INTO incident_claims"
            " (incident_key, trigger_source, status, claimed_at, completed_at, session_id)"
            " VALUES (%s, %s, 'claimed', NOW(), NULL, NULL)"
            " ON CONFLICT (incident_key) DO UPDATE SET"
            " trigger_source = EXCLUDED.trigger_source, status = 'claimed',"
            " claimed_at = NOW(), completed_at = NULL, session_id = NULL"
            " WHERE COALESCE(incident_claims.completed_at, incident_claims.claimed_at)"
            " < NOW() - (%s * INTERVAL '1 minute')"
            " RETURNING incident_key",
            incident_key,
            trigger_source,
            within_minutes,
        )
        return row is not None

    async def complete_incident(
        self,
        incident_key: str,
        status: str = "completed",
        session_id: str | None = None,
    ) -> None:
        await self._exec(
            "INSERT INTO incident_claims"
            " (incident_key, trigger_source, status, session_id, claimed_at, completed_at)"
            " VALUES (%s, 'unknown', %s, %s, NOW(), NOW())"
            " ON CONFLICT (incident_key) DO UPDATE SET"
            " status = EXCLUDED.status, session_id = EXCLUDED.session_id, completed_at = NOW()",
            incident_key,
            status,
            uuid.UUID(session_id) if session_id else None,
        )

    async def release_incident(self, incident_key: str) -> None:
        await self._exec(
            "DELETE FROM incident_claims WHERE incident_key = %s AND status = 'claimed'",
            incident_key,
        )

    async def is_incident_claimed(self, incident_key: str, within_minutes: int = 3) -> bool:
        row = await self._fetchrow(
            "SELECT 1 FROM incident_claims WHERE incident_key = %s"
            " AND COALESCE(completed_at, claimed_at) > NOW() - (%s * INTERVAL '1 minute')"
            " LIMIT 1",
            incident_key,
            within_minutes,
        )
        return row is not None

    async def get_alerts(self, limit: int = 50) -> list[dict]:
        import json as _json

        rows = await self._fetchall(
            "SELECT id, service, error, resolution, confidence, sns_sent, status,"
            "       created_at, session_id, trigger_source, dedup_key, evidence"
            " FROM alerts ORDER BY created_at DESC LIMIT %s",
            min(limit, 200),
        )
        return [
            {
                "id": str(r["id"]),
                "service": r["service"],
                "error": r["error"],
                "resolution": r["resolution"],
                "confidence": r["confidence"],
                "sns_sent": bool(r["sns_sent"]),
                "status": r["status"],
                "timestamp": r["created_at"].isoformat() if r["created_at"] else None,
                "session_id": str(r["session_id"]) if r["session_id"] else None,
                "trigger_source": r["trigger_source"],
                "dedup_key": r["dedup_key"],
                "evidence": _json.loads(r["evidence"]) if r.get("evidence") else [],
            }
            for r in rows
        ]

    async def get_alert(self, alert_id: str) -> dict | None:
        import json as _json

        row = await self._fetchrow(
            "SELECT id, service, error, resolution, confidence, sns_sent, status,"
            "       created_at, session_id, trigger_source, dedup_key, evidence"
            " FROM alerts WHERE id = %s",
            uuid.UUID(alert_id),
        )
        if not row:
            return None
        notif_rows = await self._fetchall(
            "SELECT channel, status, error, sent_at FROM alert_notifications"
            " WHERE alert_id = %s ORDER BY sent_at ASC",
            uuid.UUID(alert_id),
        )
        return {
            "id": str(row["id"]),
            "service": row["service"],
            "error": row["error"],
            "resolution": row["resolution"],
            "confidence": row["confidence"],
            "sns_sent": bool(row["sns_sent"]),
            "status": row["status"],
            "timestamp": row["created_at"].isoformat() if row["created_at"] else None,
            "session_id": str(row["session_id"]) if row["session_id"] else None,
            "trigger_source": row["trigger_source"],
            "dedup_key": row["dedup_key"],
            "evidence": _json.loads(row["evidence"]) if row.get("evidence") else [],
            "notifications": [
                {
                    "channel": n["channel"],
                    "status": n["status"],
                    "error": n["error"],
                    "sent_at": n["sent_at"].isoformat() if n["sent_at"] else None,
                }
                for n in notif_rows
            ],
        }

    async def get_app_config(self, key: str) -> dict | None:
        row = await self._fetchrow("SELECT value FROM app_config WHERE key = %s", key)
        return row["value"] if row else None

    async def set_app_config(self, key: str, value: dict) -> None:
        await self._exec(
            "INSERT INTO app_config (key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()",
            key,
            self._jsonb(value),
        )

    async def search_sessions(self, query: str, limit: int = 10) -> list[dict]:
        if not query.strip():
            return []
        rows = await self._fetchall(
            """
            SELECT id, title, last_active_at, model, snippet
            FROM (
                SELECT DISTINCT ON (s.id)
                    s.id, s.title, s.last_active_at, s.model,
                    LEFT(m.content, 200) AS snippet
                FROM sessions s
                JOIN messages m ON m.session_id = s.id AND m.role = 'user'
                WHERE s.is_deleted = FALSE
                  AND (s.title ILIKE '%%' || %s || '%%' OR m.content ILIKE '%%' || %s || '%%')
                ORDER BY s.id, m.created_at ASC
            ) sub ORDER BY last_active_at DESC LIMIT %s
        """,
            query,
            query,
            min(limit, 20),
        )
        return [
            {
                "id": str(r["id"]),
                "title": r["title"],
                "last_active_at": r["last_active_at"].isoformat() if r["last_active_at"] else None,
                "model": r["model"],
                "snippet": r["snippet"],
            }
            for r in rows
        ]
