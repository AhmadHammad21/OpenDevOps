"""Database layer — PostgreSQL connection pool, checkpointer, and row-save helpers."""

from __future__ import annotations

import uuid
from typing import Any

from loguru import logger

from agent.config import settings


class Database:
    """Wraps the async connection pool, LangGraph checkpointer, and all write helpers."""

    def __init__(self) -> None:
        self._pool: Any = None
        self._checkpointer: Any = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def init(self) -> Any:
        """
        Open the connection pool and set up the LangGraph checkpointer.
        Returns the checkpointer so the caller can pass it to init_agent().
        Falls back to MemorySaver when DATABASE_URL is not configured.
        """
        if not settings.database_url:
            logger.warning("DATABASE_URL not set — using in-memory checkpointer (no persistence)")
            return self._use_memory()

        try:
            import psycopg  # type: ignore
            from psycopg_pool import AsyncConnectionPool
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            # prepare_threshold=None disables psycopg3 auto-prepared statements,
            # required for PgBouncer/Supabase connection poolers (transaction mode).
            self._pool = AsyncConnectionPool(
                conninfo=settings.database_url,
                open=False,
                kwargs={"prepare_threshold": None},
            )
            await self._pool.open()
            self._checkpointer = AsyncPostgresSaver(self._pool)

            # CREATE INDEX CONCURRENTLY cannot run inside a transaction — use a
            # dedicated autocommit connection just for the one-time setup call.
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
            logger.error("DB init failed ({}) — falling back to MemorySaver", e)
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

    # ── Low-level helpers ────────────────────────────────────────────────────
    # psycopg3 uses %s placeholders (not $1/$2). Dicts are wrapped with Jsonb()
    # so psycopg knows to serialise them as JSONB rather than text.

    @staticmethod
    def _jsonb(value: Any) -> Any:
        """Wrap a dict/list in Jsonb so psycopg3 sends it as JSONB."""
        from psycopg.types.json import Jsonb  # type: ignore
        return Jsonb(value)

    async def _exec(self, query: str, *params: Any) -> None:
        """Execute a write query. No-op if pool is unavailable."""
        if self._pool is None:
            return
        try:
            async with self._pool.connection() as conn:
                await conn.execute(query, params)
        except Exception as e:
            logger.error("DB write failed: {}", e)

    async def _fetchall(self, query: str, *params: Any) -> list[dict]:
        """Fetch all rows as a list of dicts. Returns [] if pool is unavailable."""
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
        """Fetch a single row as a dict. Returns None if pool is unavailable."""
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

    # ── App table helpers ─────────────────────────────────────────────────────

    async def upsert_session(
        self,
        session_id: str,
        model: str,
        aws_region: str,
        title: str | None = None,
    ) -> None:
        """Create session on first turn; refresh last_active_at on every turn."""
        await self._exec(
            """
            INSERT INTO sessions (id, title, model, aws_region)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                last_active_at = NOW(),
                model = EXCLUDED.model
            """,
            uuid.UUID(session_id),
            title,
            model,
            aws_region,
        )

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> str:
        """Insert a message row and return its UUID string."""
        msg_id = str(uuid.uuid4())
        await self._exec(
            """
            INSERT INTO messages (id, session_id, role, content, metadata)
            VALUES (%s, %s, %s, %s, %s)
            """,
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

    async def list_sessions(self) -> list[dict]:
        """Return non-deleted sessions ordered by most recently active."""
        rows = await self._fetchall(
            "SELECT id, title, last_active_at, model FROM sessions WHERE is_deleted = FALSE ORDER BY last_active_at DESC"
        )
        return [
            {
                "id": str(r["id"]),
                "title": r["title"],
                "last_active_at": r["last_active_at"].isoformat() if r["last_active_at"] else None,
                "model": r["model"],
            }
            for r in rows
        ]

    async def get_messages(self, session_id: str) -> list[dict]:
        """Return messages enriched with tool_calls and usage per assistant message.
        Returns [] if the session is soft-deleted or does not exist."""
        uid = uuid.UUID(session_id)

        session = await self._fetchrow(
            "SELECT is_deleted FROM sessions WHERE id = %s", uid
        )
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
            tc_by_msg.setdefault(mid, []).append({
                "tool_name": tc["tool_name"],
                "args": tc["args"],
                "result": tc["result"],
                "error": tc["error"],
            })

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
                "role": msg["role"],
                "content": msg["content"],
                "created_at": msg["created_at"].isoformat() if msg["created_at"] else None,
            }
            if msg["role"] == "assistant":
                item["tool_calls"] = tc_by_msg.get(mid, [])
                item["usage"] = usage_by_msg.get(mid)
            result.append(item)

        return result

    async def delete_session(self, session_id: str) -> None:
        """Soft-delete a session — hidden from UI, data preserved for the cleanup job."""
        await self._exec(
            "UPDATE sessions SET is_deleted = TRUE, deleted_at = NOW() WHERE id = %s",
            uuid.UUID(session_id),
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
    ) -> None:
        await self._exec(
            """
            INSERT INTO usage_events
                (session_id, message_id, model, input_tokens, output_tokens,
                 cost_usd, latency_ms, tool_call_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            uuid.UUID(session_id),
            uuid.UUID(message_id) if message_id else None,
            model,
            input_tokens,
            output_tokens,
            cost_usd,
            latency_ms,
            tool_call_count,
        )


# Module-level singleton — import this everywhere
db = Database()
