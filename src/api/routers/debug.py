"""Temporary debug endpoint — remove before merging to main."""

from fastapi import APIRouter

from agent.db import db
from config import settings

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/auth")
async def debug_auth() -> dict:
    jwt_secret = settings.jwt_secret
    user_count = await db.count_users()
    return {
        "jwt_secret_set": bool(jwt_secret),
        "jwt_secret_preview": (jwt_secret[:4] + "…") if jwt_secret else None,
        "jwt_expire_minutes": settings.jwt_expire_minutes,
        "checkpoint_backend": settings.checkpoint_backend,
        "database_url_set": bool(settings.database_url),
        "user_count": user_count,
    }
