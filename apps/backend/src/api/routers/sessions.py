"""Session management endpoints."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from agent.db import db
from models.sessions import MessageRecord, SessionSummary

router = APIRouter(prefix="/sessions", tags=["sessions"])


class RenameRequest(BaseModel):
    title: str


@router.get("", response_model=list[SessionSummary])
async def list_sessions(
    limit: int = Query(default=15, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[SessionSummary]:
    return await db.list_sessions(limit=limit, offset=offset)


@router.get("/{session_id}/messages", response_model=list[MessageRecord])
async def get_session_messages(session_id: str) -> list[MessageRecord]:
    return await db.get_messages(session_id)


@router.patch("/{session_id}")
async def rename_session(session_id: str, body: RenameRequest) -> dict:
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    await db.rename_session(session_id, title)
    return {"session_id": session_id, "title": title}


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> dict:
    await db.delete_session(session_id)
    return {"deleted": session_id}
