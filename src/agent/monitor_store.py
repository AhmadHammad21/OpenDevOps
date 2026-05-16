"""Monitor store — persists alerts and tracks service status."""

from __future__ import annotations

from datetime import UTC, datetime

from loguru import logger

# In-memory service status (ephemeral — just current state)
_services: dict[str, dict] = {}


async def add_alert(
    service: str,
    error: str,
    resolution: str,
    confidence: str,
    sns_sent: bool,
) -> str:
    """Persist an alert to the DB backend."""
    from agent.db import db

    try:
        return await db.add_alert(service, error, resolution, confidence, sns_sent)
    except Exception as e:
        logger.error("Failed to persist alert: {}", e)
        return ""


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
