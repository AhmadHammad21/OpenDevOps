"""Monitoring API — service health status and persisted alerts."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from agent.monitor_store import get_alerts_async, get_alert_async, get_services
from api.auth import get_current_user

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/services")
async def services(
    _user: Annotated[dict | None, Depends(get_current_user)],
) -> list:
    return get_services()


@router.get("/alerts")
async def alerts(
    _user: Annotated[dict | None, Depends(get_current_user)],
    limit: int = 50,
) -> list:
    return await get_alerts_async(limit)


@router.get("/alerts/{alert_id}")
async def alert_detail(
    alert_id: str,
    _user: Annotated[dict | None, Depends(get_current_user)],
) -> dict:
    alert = await get_alert_async(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert
