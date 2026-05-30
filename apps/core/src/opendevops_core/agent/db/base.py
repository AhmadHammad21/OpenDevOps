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
        source: str = "chat",
        org_id: str | None = None,
        user_id: str | None = None,
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
    async def list_sessions(
        self, limit: int = 15, offset: int = 0, org_id: str | None = None
    ) -> list[dict]: ...

    async def get_session_model(self, session_id: str) -> str | None:
        """Return the LLM model the session was created with, or None if the session
        doesn't exist yet. Used by the chat router to pin existing chats to their
        original model when the user changes the Settings picker.

        Default returns None — backends override when they can answer cheaply."""
        return None

    @abstractmethod
    async def get_messages(self, session_id: str, org_id: str | None = None) -> list[dict]: ...

    @abstractmethod
    async def delete_session(self, session_id: str) -> None: ...

    @abstractmethod
    async def rename_session(self, session_id: str, title: str) -> None: ...

    # ── Analytics ──────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_dashboard_stats(self, org_id: str | None = None) -> dict: ...

    @abstractmethod
    async def get_history_stats(self, days: int = 30, org_id: str | None = None) -> dict: ...

    @abstractmethod
    async def search_sessions(
        self, query: str, limit: int = 10, org_id: str | None = None
    ) -> list[dict]: ...

    # ── User / auth ────────────────────────────────────────────────────────────
    # Default implementations return empty/zero — real auth requires PostgreSQL.

    async def count_users(self) -> int:
        return 0

    async def get_user_by_email(self, email: str) -> dict | None:
        return None

    async def get_user_by_id(self, user_id: str) -> dict | None:
        return None

    async def create_org(self, name: str, slug: str) -> dict | None:
        return None

    async def get_first_org(self) -> dict | None:
        return None

    async def create_user(
        self,
        email: str,
        name: str,
        password_hash: str,
        role: str,
        org_id: str | None = None,
    ) -> dict | None:
        return None

    async def list_users(self, org_id: str | None = None) -> list[dict]:
        return []

    async def update_user(self, user_id: str, **fields: Any) -> dict | None:
        return None

    async def assign_org_to_users_without_org(self, org_id: str) -> None:
        pass

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
        dedup_key: str | None = None,
        status: str = "completed",
        session_id: str | None = None,
        trigger_source: str | None = None,
        evidence: list | None = None,
    ) -> str:
        return ""

    async def add_notification(
        self,
        alert_id: str,
        channel: str,
        status: str = "attempted",
        error: str | None = None,
    ) -> None:
        pass

    async def is_recent_alert(self, dedup_key: str, within_minutes: int = 3) -> bool:
        return False

    async def claim_incident(
        self,
        incident_key: str,
        trigger_source: str,
        within_minutes: int = 3,
    ) -> bool:
        return False

    async def complete_incident(
        self,
        incident_key: str,
        status: str = "completed",
        session_id: str | None = None,
    ) -> None:
        pass

    async def release_incident(self, incident_key: str) -> None:
        pass

    async def is_incident_claimed(self, incident_key: str, within_minutes: int = 3) -> bool:
        return False

    async def get_alerts(self, limit: int = 50, org_id: str | None = None) -> list[dict]:
        return []

    async def get_alert(self, alert_id: str, org_id: str | None = None) -> dict | None:
        return None

    # ── Cloud accounts (per-org/per-install credential configs) ───────────────
    # Default: no rows -> the credential resolver falls back to env/profile creds.
    # Only the Postgres backend persists these today (the product's multi-tenant DB).

    async def get_cloud_accounts(self, org_id: str | None = None) -> list[dict]:
        return []

    async def get_default_cloud_account(
        self, org_id: str | None = None, provider: str = "aws"
    ) -> dict | None:
        return None

    async def get_cloud_account(
        self, account_id: str, org_id: str | None = None
    ) -> dict | None:
        return None

    async def create_cloud_account(
        self,
        org_id: str | None,
        provider: str,
        auth_method: str,
        label: str,
        region: str | None,
        config: dict,
        secret_enc: str | None = None,
    ) -> dict | None:
        return None

    async def set_cloud_account_status(
        self, account_id: str, status: str, status_detail: str | None = None
    ) -> None:
        pass

    async def delete_cloud_account(self, account_id: str, org_id: str | None = None) -> None:
        pass

    # ── App config (init wizard / infrastructure state) ──────────────────────

    async def get_app_config(self, key: str) -> dict | None:
        return None

    async def set_app_config(self, key: str, value: dict) -> None:
        pass
