"""Assertive tests for Telegram message rendering and bot API delivery."""

from __future__ import annotations

import asyncio

from opendevops_core.integrations.telegram import (
    _build_message,
    post_failed_investigation,
    post_investigation,
)

SAMPLE_RESULT = {
    "root_cause_category": "RESOURCE_LIMIT",
    "root_cause_summary": "Lambda exhausted memory under burst traffic.",
    "confidence": "HIGH",
    "evidence": [
        "MemoryUtilization reached 99%",
        "OOM errors spiked in CloudWatch logs",
    ],
    "mitigation_steps": [
        "Increase Lambda memory",
        "Add memory alarm at 80%",
    ],
    "services_affected": ["Lambda", "CloudWatch"],
}


def test_build_message_contains_confidence_category_and_summary():
    text = _build_message(SAMPLE_RESULT, "session-1234")

    assert "HIGH" in text
    assert "RESOURCE_LIMIT" in text
    assert "Lambda exhausted memory" in text
    assert "session-1234"[:8] in text


def test_build_message_test_flag_adds_test_header():
    text = _build_message(SAMPLE_RESULT, "session-abcd", is_test=True)
    assert "[TEST]" in text


def test_build_message_includes_mitigation_steps():
    text = _build_message(SAMPLE_RESULT, "session-1234")
    assert "Increase Lambda memory" in text
    assert "Add memory alarm at 80%" in text


def test_build_message_includes_services_affected():
    text = _build_message(SAMPLE_RESULT, "session-1234")
    assert "Lambda" in text
    assert "CloudWatch" in text


def _make_fake_client(captured: dict, status: int = 200):
    class FakeResponse:
        status_code = status
        text = "ok" if status == 200 else "error"

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = (exc_type, exc, tb)

        async def post(self, url, json):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    return FakeClient


def test_post_investigation_sends_to_bot_api(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr("httpx.AsyncClient", _make_fake_client(captured))

    result = asyncio.run(
        post_investigation(
            bot_token="123456:TEST-TOKEN",
            chat_id="-100123456789",
            result=SAMPLE_RESULT,
            session_id="session-1234",
        )
    )

    assert result is True
    assert "api.telegram.org" in captured["url"]
    assert "123456:TEST-TOKEN" in captured["url"]
    assert captured["json"]["chat_id"] == "-100123456789"
    assert captured["json"]["parse_mode"] == "HTML"
    assert "Lambda exhausted memory" in captured["json"]["text"]


def test_post_investigation_returns_false_on_non_200(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr("httpx.AsyncClient", _make_fake_client(captured, status=400))

    result = asyncio.run(
        post_investigation(
            bot_token="123456:TEST-TOKEN",
            chat_id="-100123456789",
            result=SAMPLE_RESULT,
            session_id="session-1234",
        )
    )

    assert result is False


def test_post_failed_investigation_sends_service_and_error(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr("httpx.AsyncClient", _make_fake_client(captured))

    result = asyncio.run(
        post_failed_investigation(
            bot_token="123456:TEST-TOKEN",
            chat_id="-100123456789",
            service="payment-service",
            error="Agent timeout after 120s",
            session_id="session-abcd",
        )
    )

    assert result is True
    assert "payment-service" in captured["json"]["text"]
    assert "Agent timeout after 120s" in captured["json"]["text"]
    assert "⚠️" in captured["json"]["text"]
