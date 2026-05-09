"""Monitor store — persists alerts and tracks service status."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from loguru import logger

# In-memory service status (ephemeral — just current state)
_services: dict[str, dict] = {}


def add_alert(service: str, error: str, resolution: str, confidence: str, sns_sent: bool) -> None:
    """Persist an alert to the DB backend. Called from async context."""
    from agent.db import db

    async def _save() -> None:
        await db.add_alert(service, error, resolution, confidence, sns_sent)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_save())
        else:
            loop.run_until_complete(_save())
    except Exception as e:
        logger.error("Failed to persist alert: {}", e)


def update_service(name: str, status: str, error: str | None = None) -> None:
    _services[name] = {
        "name": name,
        "status": status,
        "last_check": datetime.now(UTC).isoformat(),
        "last_error": error,
    }


async def get_alerts_async(limit: int = 50) -> list[dict]:
    from agent.db import db
    return await db.get_alerts(limit)


async def get_alert_async(alert_id: str) -> dict | None:
    from agent.db import db
    return await db.get_alert(alert_id)


def get_services() -> list[dict]:
    return list(_services.values())
