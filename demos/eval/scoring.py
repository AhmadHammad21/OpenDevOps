"""Pure scoring functions for the eval runner.

Kept side-effect-free so they can be unit-tested without standing up AWS state
or hitting the agent. Each scorer returns a (bool, str) tuple — pass/fail plus
a one-line reason that lands in the run report.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ScenarioResult:
    """What the runner produces per scenario after one full run."""

    scenario_id: str
    passed: bool
    reasons: list[str]
    # Soft metrics
    latency_ms: int
    tool_call_count: int
    cost_usd: float | None
    input_tokens: int
    output_tokens: int
    model: str
    # The raw agent output (so the report can include the actual root cause)
    agent_root_cause_category: str
    agent_root_cause_summary: str
    error: str | None = None


def _norm(s: str) -> str:
    return s.lower().replace("aws ", "").replace("amazon ", "").strip()


def check_root_cause_category(
    actual: str, expected: str | list[str]
) -> tuple[bool, str]:
    """Match the agent's category against one (str) or several (list) acceptable values.

    Many real incidents are defensibly classifiable in more than one way — e.g. a
    Lambda crashing on a missing key is both ``COMPONENT_FAILURE`` (the component
    is broken) and ``SYSTEM_CHANGE`` (the recent deploy introduced the bug). The
    ground truth can list every defensible answer; the agent matches if it picks
    any of them.
    """
    a = (actual or "").strip().upper()
    if isinstance(expected, str):
        valid = [expected.strip().upper()]
    else:
        valid = [e.strip().upper() for e in (expected or []) if e]
    ok = a in valid
    return ok, (
        f"root_cause_category match: {actual}" if ok
        else f"root_cause_category={actual!r} (expected any of {valid})"
    )


def check_services_affected(
    actual: list[str], expected: list[str]
) -> tuple[bool, str]:
    """At least one expected service must appear in the agent's list. Tolerant:
    case-insensitive substring + the 'AWS '/'Amazon ' prefix is stripped so
    'Lambda' matches 'AWS Lambda'."""
    actual_n = [_norm(s) for s in actual or []]
    matches = [e for e in expected if any(_norm(e) in a or a in _norm(e) for a in actual_n)]
    ok = len(matches) > 0
    return ok, (
        f"services match: {matches}" if ok
        else f"no service overlap (agent={actual} vs expected={expected})"
    )


def check_evidence_keywords(
    evidence: list[str], keywords: list[str], min_ratio: float = 0.5
) -> tuple[bool, str]:
    """At least `min_ratio` of expected keywords must appear in the evidence
    text (case-insensitive). Pins the cause — the agent should mention the
    actual error / config / number, not just generic boilerplate."""
    if not keywords:
        return True, "no keywords to check"
    joined = " ".join(evidence or []).lower()
    hits = [kw for kw in keywords if kw.lower() in joined]
    ratio = len(hits) / len(keywords)
    ok = ratio >= min_ratio
    return ok, (
        f"evidence keywords {len(hits)}/{len(keywords)} found: {hits}" if ok
        else f"evidence keywords {len(hits)}/{len(keywords)} (need {min_ratio:.0%}): "
        f"missed {[k for k in keywords if k not in hits]}"
    )


def check_tools_called(
    called: list[str], expected_any_of: list[str]
) -> tuple[bool, str]:
    """The agent must have used at least one of the expected tools. Pins the
    methodology — e.g. a runtime error MUST be diagnosed via log inspection,
    not vibes."""
    if not expected_any_of:
        return True, "no tool expectations"
    overlap = [t for t in expected_any_of if t in (called or [])]
    ok = len(overlap) > 0
    return ok, (
        f"called expected tool(s): {overlap}" if ok
        else f"none of the expected tools called (expected any of {expected_any_of}, "
        f"agent called {called or []})"
    )


def score(
    scenario_id: str,
    agent_output: dict[str, Any],
    ground_truth: dict[str, Any],
    metrics: dict[str, Any],
) -> ScenarioResult:
    """Apply every check; build a ScenarioResult.

    agent_output is the parsed args of the submit_investigation tool call, e.g.
        {"root_cause_category": "COMPONENT_FAILURE",
         "root_cause_summary": "Lambda KeyError on user_id",
         "evidence": ["traceback line 12 ...", "8/8 invocations failed"],
         "services_affected": ["Lambda"],
         ...}

    Tolerance choices:
    * Agents frequently fill ``services_affected`` with the affected RESOURCE
      name ("opendevops-demo-crashing") rather than the service category
      ("Lambda"). The summary text usually mentions the service — so we
      additionally match expected services against the summary.
    * The structured ``evidence`` list can be sparse while the ``root_cause_summary``
      contains the diagnostic prose. Keyword matching scans both.
    """
    summary = (agent_output.get("root_cause_summary") or "").strip()
    raw_services = agent_output.get("services_affected") or []
    raw_evidence = agent_output.get("evidence") or []

    # Include the summary as a synthetic "service" entry so substring-matching
    # picks up service names mentioned in prose (Lambda, ECS, DynamoDB, ...).
    services_for_match = list(raw_services) + ([summary] if summary else [])
    # Same for evidence: scan summary + evidence list together.
    evidence_for_match = list(raw_evidence) + ([summary] if summary else [])

    checks = [
        check_root_cause_category(
            agent_output.get("root_cause_category", ""),
            ground_truth.get("root_cause_category", ""),
        ),
        check_services_affected(
            services_for_match,
            ground_truth.get("services_affected") or [],
        ),
        check_evidence_keywords(
            evidence_for_match,
            ground_truth.get("evidence_keywords") or [],
        ),
        check_tools_called(
            metrics.get("tools_called") or [],
            ground_truth.get("expected_tools_any_of") or [],
        ),
    ]
    passed = all(ok for ok, _ in checks)
    return ScenarioResult(
        scenario_id=scenario_id,
        passed=passed,
        reasons=[msg for _, msg in checks],
        latency_ms=int(metrics.get("latency_ms", 0)),
        tool_call_count=int(metrics.get("tool_call_count", 0)),
        cost_usd=metrics.get("cost_usd"),
        input_tokens=int(metrics.get("input_tokens", 0)),
        output_tokens=int(metrics.get("output_tokens", 0)),
        model=metrics.get("model", ""),
        agent_root_cause_category=agent_output.get("root_cause_category", ""),
        agent_root_cause_summary=agent_output.get("root_cause_summary", ""),
    )
