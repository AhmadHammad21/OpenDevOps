"""History endpoints — cross-session analytics for the frontend."""

from __future__ import annotations

from fastapi import APIRouter, Query

from agent.db import db

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
async def get_history(days: int = Query(default=30, ge=1, le=365)) -> dict:
    return await db.get_history_stats(days)


@router.get("/search")
async def search_history(
    q: str = Query(default=""),
    limit: int = Query(default=10, ge=1, le=20),
) -> dict:
    results = await db.search_sessions(q, limit)
    return {"results": results, "count": len(results)}
