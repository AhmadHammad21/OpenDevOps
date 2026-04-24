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
            from psycopg_pool import AsyncConnectionPool
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            self._pool = AsyncConnectionPool(conninfo=settings.database_url, open=False)
            await self._pool.open()
            self._checkpointer = AsyncPostgresSaver(self._pool)
            await self._checkpointer.setup()  # creates langgraph tables if missing
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

    async def _exec(self, query: str, *params: Any) -> None:
        """Execute a write query. No-op if pool is unavailable."""
        if self._pool is None:
            return
        try:
            async with self._pool.connection() as conn:
                await conn.execute(query, params)
        except Exception as e:
            logger.error("DB write failed: {}", e)

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
            VALUES ($1, $2, $3, $4)
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
            VALUES ($1, $2, $3, $4, $5)
            """,
            uuid.UUID(msg_id),
            uuid.UUID(session_id),
            role,
            content,
            metadata or {},
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
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            uuid.UUID(session_id),
            uuid.UUID(message_id) if message_id else None,
            tool_name,
            args,
            result,
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
    ) -> None:
        await self._exec(
            """
            INSERT INTO usage_events
                (session_id, message_id, model, input_tokens, output_tokens,
                 cost_usd, latency_ms, tool_call_count)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
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
