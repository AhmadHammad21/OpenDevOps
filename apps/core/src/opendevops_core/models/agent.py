"""Agent domain models — investigation input, findings, and root cause output."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RootCauseCategory(str, Enum):
    SYSTEM_CHANGE = "SYSTEM_CHANGE"
    INPUT_ANOMALY = "INPUT_ANOMALY"
    RESOURCE_LIMIT = "RESOURCE_LIMIT"
    COMPONENT_FAILURE = "COMPONENT_FAILURE"
    DEPENDENCY_ISSUE = "DEPENDENCY_ISSUE"
    UNKNOWN = "UNKNOWN"


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Investigation(BaseModel):
    description: str
    alarm_name: str | None = None
    service: str | None = None
    region: str | None = None


class Finding(BaseModel):
    hypothesis: str
    evidence: list[str] = Field(default_factory=list)
    confidence: Confidence = Confidence.LOW


class InvestigationResult(BaseModel):
    root_cause_category: RootCauseCategory = RootCauseCategory.UNKNOWN
    root_cause_summary: str = ""
    # Ranked hypotheses (most likely first), each with its own cited evidence and
    # confidence. The flat `evidence` below is retained for backward compatibility.
    hypotheses: list[Finding] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    mitigation_steps: list[str] = Field(default_factory=list)
    validation_steps: list[str] = Field(default_factory=list)
    confidence: Confidence = Confidence.LOW
    services_affected: list[str] = Field(default_factory=list)
    recommended_follow_up: str = ""
    tool_calls_made: int = 0
    raw_json: dict[str, Any] = Field(default_factory=dict)
