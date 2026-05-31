"""Unit tests for the eval scorer (demos/eval/scoring.py).

The runner itself is integration-only (hits real cloud), but the pure scoring
functions are testable. Pin the scoring contract so a contributor who edits
``scoring.py`` sees clear failures rather than mysterious eval regressions.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_EVAL_DIR = Path(__file__).resolve().parents[4] / "demos" / "eval"
sys.path.insert(0, str(_EVAL_DIR))

from scoring import (  # noqa: E402
    check_evidence_keywords,
    check_root_cause_category,
    check_services_affected,
    check_tools_called,
    score,
)


# ── individual checks ────────────────────────────────────────────────────────


def test_root_cause_match_is_exact_and_case_insensitive():
    ok, _ = check_root_cause_category("RESOURCE_LIMIT", "RESOURCE_LIMIT")
    assert ok
    ok, _ = check_root_cause_category("resource_limit", "RESOURCE_LIMIT")
    assert ok


def test_root_cause_mismatch_reports_both_values():
    ok, msg = check_root_cause_category("RESOURCE_LIMIT", "COMPONENT_FAILURE")
    assert not ok
    assert "RESOURCE_LIMIT" in msg and "COMPONENT_FAILURE" in msg


def test_root_cause_accepts_list_of_valid_categories():
    """Many incidents are defensibly classifiable two ways (a crashing Lambda is
    both COMPONENT_FAILURE and SYSTEM_CHANGE). Ground truth supports a list to
    accept any of them — the scorer shouldn't punish a defensible call."""
    ok, _ = check_root_cause_category("SYSTEM_CHANGE", ["COMPONENT_FAILURE", "SYSTEM_CHANGE"])
    assert ok
    ok, _ = check_root_cause_category("COMPONENT_FAILURE", ["COMPONENT_FAILURE", "SYSTEM_CHANGE"])
    assert ok


def test_root_cause_list_mismatch_lists_all_acceptable():
    """When the agent picks an unacceptable category, the error message has to
    show every accepted value — otherwise a contributor seeing the failure has
    no idea what was allowed."""
    ok, msg = check_root_cause_category(
        "INPUT_ANOMALY", ["COMPONENT_FAILURE", "SYSTEM_CHANGE"]
    )
    assert not ok
    assert "COMPONENT_FAILURE" in msg
    assert "SYSTEM_CHANGE" in msg


def test_services_match_strips_aws_amazon_prefixes():
    """The agent often writes "AWS Lambda" or "Amazon Lambda"; ground truth
    just says "Lambda". They should match either way."""
    ok, _ = check_services_affected(["AWS Lambda"], ["Lambda"])
    assert ok
    ok, _ = check_services_affected(["Amazon EC2"], ["EC2"])
    assert ok
    ok, _ = check_services_affected(["Lambda"], ["AWS Lambda"])
    assert ok


def test_services_no_overlap_fails():
    ok, msg = check_services_affected(["EC2"], ["Lambda"])
    assert not ok
    assert "no service overlap" in msg


def test_services_partial_overlap_passes():
    """At least ONE expected service must be present — pinning all services
    would be too strict (the agent often surfaces extras)."""
    ok, _ = check_services_affected(["Lambda", "DynamoDB"], ["Lambda"])
    assert ok


def test_evidence_keywords_case_insensitive_substring():
    evidence = ["KeyError on 'user_id'", "8/8 invocations failed"]
    ok, _ = check_evidence_keywords(evidence, ["keyerror", "user_id"])
    assert ok


def test_evidence_keywords_partial_meets_threshold():
    """Default ratio is 0.5 — half the keywords is enough."""
    evidence = ["KeyError on 'user_id' raised"]
    ok, msg = check_evidence_keywords(evidence, ["KeyError", "user_id", "fictional"])
    assert ok  # 2/3 = 0.66, above 0.5
    assert "2/3" in msg


def test_evidence_keywords_below_threshold_fails():
    evidence = ["something happened"]
    ok, msg = check_evidence_keywords(evidence, ["KeyError", "user_id", "traceback"])
    assert not ok
    assert "0/3" in msg


def test_evidence_keywords_empty_expected_passes():
    """Scenarios that don't pin keywords just skip this check."""
    ok, _ = check_evidence_keywords(["any"], [])
    assert ok


def test_tools_called_any_of_passes_on_single_overlap():
    ok, _ = check_tools_called(
        ["describe_log_groups", "get_log_events"],
        ["get_log_events", "query_logs_insights"],
    )
    assert ok


def test_tools_called_no_overlap_fails():
    ok, msg = check_tools_called(["get_alarms"], ["get_log_events"])
    assert not ok
    assert "get_log_events" in msg


def test_tools_called_empty_expectation_passes():
    ok, _ = check_tools_called(["whatever"], [])
    assert ok


# ── full score() ─────────────────────────────────────────────────────────────


@pytest.fixture
def lambda_crash_ground_truth():
    return {
        "root_cause_category": "COMPONENT_FAILURE",
        "services_affected": ["Lambda"],
        "evidence_keywords": ["KeyError", "user_id"],
        "expected_tools_any_of": ["get_log_events", "query_logs_insights"],
    }


def test_score_passing_run(lambda_crash_ground_truth):
    """A correctly-investigated Lambda crash. The agent identified the right
    category, listed Lambda, quoted the traceback, and inspected logs."""
    agent_output = {
        "root_cause_category": "COMPONENT_FAILURE",
        "root_cause_summary": "Lambda raises KeyError on 'user_id'",
        "evidence": ["traceback: KeyError on 'user_id'", "8/8 invocations failed"],
        "services_affected": ["AWS Lambda"],
    }
    metrics = {
        "tools_called": ["describe_log_groups", "get_log_events"],
        "tool_call_count": 2,
        "latency_ms": 42_000,
        "input_tokens": 5_000,
        "output_tokens": 800,
        "cost_usd": 0.018,
        "model": "openrouter/anthropic/claude-sonnet-4-6",
    }
    r = score("001_lambda_crashing", agent_output, lambda_crash_ground_truth, metrics)
    assert r.passed
    assert r.latency_ms == 42_000
    assert r.tool_call_count == 2
    assert r.cost_usd == 0.018


def test_score_fails_on_wrong_root_cause(lambda_crash_ground_truth):
    """The agent saw the right symptom but classified it as a resource limit
    instead of a component failure — that's wrong."""
    agent_output = {
        "root_cause_category": "RESOURCE_LIMIT",
        "evidence": ["traceback: KeyError on 'user_id'"],
        "services_affected": ["Lambda"],
    }
    r = score("001", agent_output, lambda_crash_ground_truth,
              {"tools_called": ["get_log_events"]})
    assert not r.passed
    assert any("RESOURCE_LIMIT" in m for m in r.reasons)


def test_score_fails_on_no_log_inspection(lambda_crash_ground_truth):
    """The agent classified correctly but never looked at the logs — it just
    guessed. Methodology check should fail."""
    agent_output = {
        "root_cause_category": "COMPONENT_FAILURE",
        "evidence": ["KeyError on user_id"],
        "services_affected": ["Lambda"],
    }
    r = score("001", agent_output, lambda_crash_ground_truth,
              {"tools_called": ["get_alarms"]})  # never checked logs
    assert not r.passed
    assert any("expected tools" in m.lower() for m in r.reasons)


def test_score_fails_on_generic_evidence(lambda_crash_ground_truth):
    """The agent classified the category right but its evidence is generic
    boilerplate that could describe any failure — keyword check fails."""
    agent_output = {
        "root_cause_category": "COMPONENT_FAILURE",
        "evidence": ["the function is broken", "errors happened"],
        "services_affected": ["Lambda"],
    }
    r = score("001", agent_output, lambda_crash_ground_truth,
              {"tools_called": ["get_log_events"]})
    assert not r.passed
    assert any("evidence" in m.lower() for m in r.reasons)


def test_score_records_soft_metrics_even_when_failing(lambda_crash_ground_truth):
    """A failure shouldn't lose the cost/latency numbers — they're how we
    track regressions even when accuracy stays at 100%."""
    r = score(
        "001",
        {"root_cause_category": "UNKNOWN", "evidence": [], "services_affected": []},
        lambda_crash_ground_truth,
        {
            "tools_called": [],
            "latency_ms": 19_000,
            "input_tokens": 1234,
            "output_tokens": 56,
            "cost_usd": 0.0012,
            "model": "openrouter/x",
        },
    )
    assert not r.passed
    assert r.latency_ms == 19_000
    assert r.input_tokens == 1234
    assert r.model == "openrouter/x"
