"""Response models for the sessions endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class SessionSummary(BaseModel):
    id: str
    title: str | None
    last_active_at: str | None
    model: str


class ToolCallRecord(BaseModel):
    tool_name: str
    args: dict
    result: dict
    error: str | None


class UsageRecord(BaseModel):
    model: str
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    latency_ms: int | None


class MessageRecord(BaseModel):
    role: str
    content: str
    created_at: str | None
    tool_calls: list[ToolCallRecord] = []
    usage: UsageRecord | None = None
