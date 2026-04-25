"""Session management endpoints."""

from fastapi import APIRouter

from agent.db import db

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
async def list_sessions():
    return await db.list_sessions()


@router.get("/{session_id}/messages")
async def get_session_messages(session_id: str):
    return await db.get_messages(session_id)


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    await db.delete_session(session_id)
    return {"deleted": session_id}
