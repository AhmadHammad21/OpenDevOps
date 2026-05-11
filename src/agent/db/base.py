"""Abstract base class shared by all storage backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DatabaseBackend(ABC):
    """Common interface for PostgreSQL, SQLite, and in-memory backends."""

    @abstractmethod
    async def init(self) -> Any:
        """Initialise the backend and return a LangGraph checkpointer."""

    @abstractmethod
    async def close(self) -> None:
        """Release resources."""

    @property
    @abstractmethod
    def checkpointer(self) -> Any:
        """Return the active LangGraph checkpointer."""

    # ── Session / message helpers ──────────────────────────────────────────────

    @abstractmethod
    async def upsert_session(
        self,
        session_id: str,
        model: str,
        aws_region: str,
        title: str | None = None,
    ) -> None: ...

    @abstractmethod
    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> str: ...

    @abstractmethod
    async def save_tool_call(
        self,
        session_id: str,
        message_id: str | None,
        tool_name: str,
        args: dict,
        result: dict,
        duration_ms: int | None = None,
    ) -> None: ...

    @abstractmethod
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
    ) -> None: ...

    @abstractmethod
    async def list_sessions(self, limit: int = 15, offset: int = 0) -> list[dict]: ...

    @abstractmethod
    async def get_messages(self, session_id: str) -> list[dict]: ...

    @abstractmethod
    async def delete_session(self, session_id: str) -> None: ...

    @abstractmethod
    async def rename_session(self, session_id: str, title: str) -> None: ...

    # ── Analytics ──────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_dashboard_stats(self) -> dict: ...

    @abstractmethod
    async def get_history_stats(self, days: int = 30) -> dict: ...

    @abstractmethod
    async def search_sessions(self, query: str, limit: int = 10) -> list[dict]: ...

    # ── User / auth ────────────────────────────────────────────────────────────
    # Default implementations return empty/zero — real auth requires PostgreSQL.

    async def count_users(self) -> int:
        return 0

    async def get_user_by_email(self, email: str) -> dict | None:
        return None

    async def get_user_by_id(self, user_id: str) -> dict | None:
        return None

    async def create_user(
        self, email: str, name: str, password_hash: str, role: str
    ) -> dict | None:
        return None

    async def list_users(self) -> list[dict]:
        return []

    async def update_user(self, user_id: str, **fields: Any) -> dict | None:
        return None

    async def delete_user(self, user_id: str) -> None:
        pass

    # ── Alerts (event-driven investigations) ──────────────────────────────────
    # Default no-op implementations — SQLite and Postgres override these.

    async def add_alert(
        self,
        service: str,
        error: str,
        resolution: str,
        confidence: str,
        sns_sent: bool,
    ) -> str:
        return ""

    async def get_alerts(self, limit: int = 50) -> list[dict]:
        return []

    async def get_alert(self, alert_id: str) -> dict | None:
        return None
