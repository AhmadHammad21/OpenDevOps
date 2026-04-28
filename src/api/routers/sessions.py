"""Session management endpoints."""

from fastapi import APIRouter

from agent.db import db
from models.sessions import MessageRecord, SessionSummary

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionSummary])
async def list_sessions() -> list[SessionSummary]:
    return await db.list_sessions()


@router.get("/{session_id}/messages", response_model=list[MessageRecord])
async def get_session_messages(session_id: str) -> list[MessageRecord]:
    return await db.get_messages(session_id)


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> dict:
    await db.delete_session(session_id)
    return {"deleted": session_id}
