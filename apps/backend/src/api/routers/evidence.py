"""Replayable evidence pack — read-only view over a session's persisted tool calls.

Joins the investigation conclusion's hypotheses to the supporting tool calls that produced
them, surfacing the exact query/command that ran plus a deterministic console deeplink.
Uses the `/api/sessions` prefix so the SPA fallback never intercepts it.
"""

from __future__ import annotations

from fastapi import APIRouter
from opendevops_core.agent.db import db
from opendevops_core.agent.evidence import build_evidence_pack

router = APIRouter(prefix="/api/sessions", tags=["evidence"])


@router.get("/{session_id}/evidence")
async def get_evidence(session_id: str) -> dict:
    raw = await db.get_evidence(session_id)
    return build_evidence_pack(session_id, raw["aws_region"], raw["tool_calls"])
