"""Final answer tool — forces the agent to submit structured investigation output."""

from typing import Literal

VALID_CATEGORIES = Literal[
    "SYSTEM_CHANGE",
    "INPUT_ANOMALY",
    "RESOURCE_LIMIT",
    "COMPONENT_FAILURE",
    "DEPENDENCY_ISSUE",
    "UNKNOWN",
]
VALID_CONFIDENCE = Literal["HIGH", "MEDIUM", "LOW"]


def submit_investigation(
    root_cause_category: VALID_CATEGORIES,
    root_cause_summary: str,
    evidence: list[str],
    mitigation_steps: list[str],
    validation_steps: list[str],
    confidence: VALID_CONFIDENCE,
    services_affected: list[str],
    recommended_follow_up: str,
    follow_up_questions: list[str],
) -> str:
    """Submit the final structured investigation result. Call this exactly once when you have
    gathered sufficient evidence and reached a conclusion. Do not output a JSON block in
    free text — call this tool instead.

    follow_up_questions: 3 short drill-down questions the user might want to ask next,
    e.g. ["What caused the spike at 14:32?", "Are retries configured on the Lambda?",
    "Has this happened before this week?"].
    """
    return "Investigation result recorded."


ALL_FINAL_ANSWER_TOOLS = [submit_investigation]
