"""Monitoring API — service health status and persisted alerts."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from agent.monitor_store import (
    get_alert_async,
    get_alerts_async,
    get_services,  # async — returns in-memory or falls back to DB
    subscribe_alerts,
    unsubscribe_alerts,
)
from api.auth import get_current_user

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/services")
async def services(
    _user: Annotated[dict | None, Depends(get_current_user)],
) -> list:
    return await get_services()


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


@router.get("/stream")
async def monitoring_stream(
    _user: Annotated[dict | None, Depends(get_current_user)],
) -> StreamingResponse:
    """SSE stream — pushes new alerts in real time as they are persisted."""

    async def generate():
        q = subscribe_alerts()
        try:
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"
            while True:
                try:
                    alert = await asyncio.wait_for(q.get(), timeout=20.0)
                    if alert is None:
                        break
                    yield f"data: {json.dumps({'type': 'alert', 'alert': alert})}\n\n"
                except TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            unsubscribe_alerts(q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
