"""Response models for the sessions endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SessionSummary(BaseModel):
    id: str
    title: str | None
    last_active_at: str | None
    model: str
    aws_region: str


class ToolCallRecord(BaseModel):
    tool_name: str
    args: dict
    result: dict | None
    error: str | None


class UsageRecord(BaseModel):
    model: str
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    latency_ms: int | None


class MessageRecord(BaseModel):
    id: str
    role: str
    content: str
    created_at: str | None
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    usage: UsageRecord | None = None
