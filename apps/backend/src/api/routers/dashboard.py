"""Dashboard stats endpoint — aggregated metrics over all sessions."""

from __future__ import annotations

from fastapi import APIRouter
from opendevops_core.agent.db import db

router = APIRouter(tags=["dashboard"])


@router.get("/stats")
async def get_stats() -> dict:
    return await db.get_dashboard_stats()
