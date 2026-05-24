"""Assertive tests for proactive poller dispatch behavior."""

from __future__ import annotations

import asyncio

from opendevops_core.agent.incident_keys import alarm_incident_key, lambda_metric_incident_key
from opendevops_core.providers.aws import poller


def test_claim_window_uses_reinvestigate_hours(monkeypatch):
    monkeypatch.setattr(poller.settings, "poll_reinvestigate_hours", 2, raising=False)
    assert poller._claim_window_minutes() == 120


def test_check_alarms_dispatches_once(monkeypatch):
    calls = {"run": 0, "persist": 0, "complete": 0}
    claimed: set[str] = set()

    def fake_get_alarms(_state):
        return {
            "alarms": [
                {
                    "name": "HighErrorRate-payment-processor",
                    "reason": "Threshold crossed",
                    "metric": "Errors",
                }
            ]
        }

    async def fake_run(prompt, session_id):
        calls["run"] += 1
        assert "HighErrorRate-payment-processor" in prompt
        return (
            {
                "root_cause_category": "RESOURCE_LIMIT",
                "root_cause_summary": "concurrency exhausted",
                "confidence": "HIGH",
                "evidence": ["throttles spiked"],
                "mitigation_steps": ["increase reserved concurrency"],
                "validation_steps": ["watch metrics"],
                "services_affected": ["Lambda"],
                "recommended_follow_up": "add alarm",
            },
            [],
        )

    async def fake_persist(_result, _tool_calls_log, _session_id, dedup_key):
        assert dedup_key == alarm_incident_key("HighErrorRate-payment-processor")
        calls["persist"] += 1

    async def fake_recent(_dedup_key, _within_minutes=3):
        return False

    async def fake_claim(key, _trigger_source, _within_minutes=3):
        if key in claimed:
            return False
        claimed.add(key)
        return True

    async def fake_complete(_key, _status="completed", _session_id=None):
        calls["complete"] += 1

    async def fake_release(_key):
        raise AssertionError("successful poller investigation should not release the claim")

    monkeypatch.setattr("opendevops_core.providers.aws.tools.cloudwatch.get_alarms", fake_get_alarms)
    monkeypatch.setattr("opendevops_core.agent.monitor_store.is_recent_alert", fake_recent)
    monkeypatch.setattr("opendevops_core.agent.monitor_store.claim_incident", fake_claim)
    monkeypatch.setattr("opendevops_core.agent.monitor_store.complete_incident", fake_complete)
    monkeypatch.setattr("opendevops_core.agent.monitor_store.release_incident", fake_release)
    monkeypatch.setattr(poller, "_run_investigation", fake_run)
    monkeypatch.setattr(poller, "_persist_and_notify", fake_persist)

    asyncio.run(poller._check_alarms())
    asyncio.run(poller._check_alarms())

    assert calls["run"] == 1
    assert calls["persist"] == 1
    assert calls["complete"] == 1


def test_check_lambda_errors_dispatches_for_threshold_breach(monkeypatch):
    calls = {"run": 0, "persist": 0, "complete": 0}

    def fake_list_lambda_functions():
        return {"functions": [{"name": "payment-processor"}]}

    def fake_get_lambda_error_rate(_name, _hours):
        return {"error_rate_pct": 12.5}

    async def fake_run(prompt, session_id):
        calls["run"] += 1
        assert "payment-processor" in prompt
        return (
            {
                "root_cause_category": "RESOURCE_LIMIT",
                "root_cause_summary": "lambda saturation",
                "confidence": "HIGH",
                "evidence": ["high throttles"],
                "mitigation_steps": ["raise concurrency"],
                "validation_steps": ["observe errors"],
                "services_affected": ["Lambda"],
                "recommended_follow_up": "right-size limits",
            },
            [],
        )

    async def fake_persist(_result, _tool_calls_log, _session_id, dedup_key):
        assert dedup_key == lambda_metric_incident_key("payment-processor")
        calls["persist"] += 1

    async def fake_claim(key, _trigger_source, _within_minutes=3):
        assert key == lambda_metric_incident_key("payment-processor")
        return True

    async def fake_complete(_key, _status="completed", _session_id=None):
        calls["complete"] += 1

    async def fake_release(_key):
        raise AssertionError("successful poller investigation should not release the claim")

    async def fake_is_claimed(_key, _within_minutes=3):
        return False

    monkeypatch.setattr("opendevops_core.providers.aws.tools.lambda_.list_lambda_functions", fake_list_lambda_functions)
    monkeypatch.setattr("opendevops_core.providers.aws.tools.lambda_.get_lambda_error_rate", fake_get_lambda_error_rate)
    monkeypatch.setattr("opendevops_core.agent.monitor_store.claim_incident", fake_claim)
    monkeypatch.setattr("opendevops_core.agent.monitor_store.complete_incident", fake_complete)
    monkeypatch.setattr("opendevops_core.agent.monitor_store.release_incident", fake_release)
    monkeypatch.setattr("opendevops_core.agent.monitor_store.is_incident_claimed", fake_is_claimed)
    monkeypatch.setattr(poller, "_run_investigation", fake_run)
    monkeypatch.setattr(poller, "_persist_and_notify", fake_persist)
    monkeypatch.setattr(poller.settings, "poll_error_threshold", 5.0, raising=False)

    asyncio.run(poller._check_lambda_errors())

    assert calls["run"] == 1
    assert calls["persist"] == 1
    assert calls["complete"] == 1
