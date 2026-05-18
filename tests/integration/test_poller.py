"""Assertive tests for proactive poller dispatch behavior."""

from __future__ import annotations

import asyncio

from agent import poller


def test_should_investigate_respects_cooldown():
    poller._last_investigated.clear()
    key = "alarm:HighErrorRate"

    assert poller._should_investigate(key) is True
    poller._mark_investigated(key)
    assert poller._should_investigate(key) is False


def test_check_alarms_dispatches_once(monkeypatch):
    poller._last_investigated.clear()
    calls = {"run": 0, "persist": 0}

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

    async def fake_persist(_result, _tool_calls_log, _session_id, _dedup_key):
        calls["persist"] += 1

    monkeypatch.setattr("tools.cloudwatch.get_alarms", fake_get_alarms)
    monkeypatch.setattr(poller, "_run_investigation", fake_run)
    monkeypatch.setattr(poller, "_persist_and_notify", fake_persist)

    asyncio.run(poller._check_alarms())
    asyncio.run(poller._check_alarms())

    assert calls["run"] == 1
    assert calls["persist"] == 1


def test_check_lambda_errors_dispatches_for_threshold_breach(monkeypatch):
    poller._last_investigated.clear()
    calls = {"run": 0, "persist": 0}

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

    async def fake_persist(_result, _tool_calls_log, _session_id, _dedup_key):
        calls["persist"] += 1

    monkeypatch.setattr("tools.lambda_.list_lambda_functions", fake_list_lambda_functions)
    monkeypatch.setattr("tools.lambda_.get_lambda_error_rate", fake_get_lambda_error_rate)
    monkeypatch.setattr(poller, "_run_investigation", fake_run)
    monkeypatch.setattr(poller, "_persist_and_notify", fake_persist)
    monkeypatch.setattr(poller.settings, "poll_error_threshold", 5.0, raising=False)

    asyncio.run(poller._check_lambda_errors())

    assert calls["run"] == 1
    assert calls["persist"] == 1
