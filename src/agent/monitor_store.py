"""Monitor store — persists alerts and tracks service status."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from loguru import logger

# In-memory service status (ephemeral — just current state)
_services: dict[str, dict] = {}

# SSE subscribers — one Queue per connected /api/monitoring/stream client
_alert_subscribers: set[asyncio.Queue[dict | None]] = set()


def subscribe_alerts() -> asyncio.Queue[dict | None]:
    q: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=50)
    _alert_subscribers.add(q)
    return q


def unsubscribe_alerts(q: asyncio.Queue[dict | None]) -> None:
    _alert_subscribers.discard(q)


def _broadcast_alert(alert: dict) -> None:
    for q in list(_alert_subscribers):
        try:
            q.put_nowait(alert)
        except asyncio.QueueFull:
            pass


async def add_alert(
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
    """Persist an alert to the DB backend and broadcast to SSE subscribers."""
    from agent.db import db

    try:
        alert_id = await db.add_alert(
            service, error, resolution, confidence, sns_sent,
            dedup_key, status, session_id, trigger_source, evidence,
        )
        if alert_id and _alert_subscribers:
            _broadcast_alert({
                "id": alert_id,
                "service": service,
                "error": error,
                "resolution": resolution,
                "confidence": confidence,
                "sns_sent": sns_sent,
                "timestamp": datetime.now(UTC).isoformat(),
                "dedup_key": dedup_key,
                "status": status,
                "trigger_source": trigger_source,
                "session_id": session_id,
                "evidence": evidence or [],
            })
        return alert_id
    except Exception as e:
        logger.error("Failed to persist alert: {}", e)
        return ""


async def add_notification(
    alert_id: str,
    channel: str,
    status: str = "attempted",
    error: str | None = None,
) -> None:
    """Record a delivery attempt for a channel against an alert."""
    from agent.db import db

    try:
        await db.add_notification(alert_id, channel, status, error)
    except Exception as e:
        logger.error("Failed to persist notification: {}", e)


async def is_recent_alert(dedup_key: str, within_minutes: int = 3) -> bool:
    """Return True if an alert with this dedup_key was saved within the last N minutes."""
    from agent.db import db

    try:
        return await db.is_recent_alert(dedup_key, within_minutes)
    except Exception:
        return False


async def claim_incident(
    incident_key: str,
    trigger_source: str,
    within_minutes: int = 3,
) -> bool:
    """Atomically claim an incident before running an investigation."""
    from agent.db import db

    try:
        return await db.claim_incident(incident_key, trigger_source, within_minutes)
    except Exception as e:
        logger.error("Failed to claim incident {}: {}", incident_key, e)
        return False


async def complete_incident(
    incident_key: str,
    status: str = "completed",
    session_id: str | None = None,
) -> None:
    from agent.db import db

    try:
        await db.complete_incident(incident_key, status, session_id)
    except Exception as e:
        logger.error("Failed to complete incident {}: {}", incident_key, e)


async def release_incident(incident_key: str) -> None:
    from agent.db import db

    try:
        await db.release_incident(incident_key)
    except Exception as e:
        logger.error("Failed to release incident {}: {}", incident_key, e)


async def is_incident_claimed(incident_key: str, within_minutes: int = 3) -> bool:
    from agent.db import db

    try:
        return await db.is_incident_claimed(incident_key, within_minutes)
    except Exception:
        return False


def update_service(name: str, status: str, error: str | None = None) -> None:
    _services[name] = {
        "name": name,
        "status": "error" if status == "failed" else "healthy",
        "last_check": datetime.now(UTC).isoformat(),
        "last_error": error,
    }


async def get_alerts_async(limit: int = 50) -> list[dict]:
    from agent.db import db

    return await db.get_alerts(limit)


async def get_alert_async(alert_id: str) -> dict | None:
    from agent.db import db

    return await db.get_alert(alert_id)


async def get_services() -> list[dict]:
    """Return service health. Uses in-memory dict if populated; falls back to DB on restart."""
    if _services:
        return list(_services.values())
    # After restart the dict is empty — derive last-known status per service from persisted alerts.
    alerts = await get_alerts_async(limit=200)
    seen: dict[str, dict] = {}
    for a in alerts:
        svc = a.get("service") or ""
        if svc and svc not in seen:
            alert_status = a.get("status", "completed")
            seen[svc] = {
                "name": svc,
                "status": "error" if alert_status == "failed" else "healthy",
                "last_check": a.get("timestamp") or "",
                "last_error": a.get("error") if alert_status == "failed" else None,
            }
    return list(seen.values())
