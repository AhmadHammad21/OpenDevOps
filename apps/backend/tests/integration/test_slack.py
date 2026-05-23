"""Assertive tests for Slack payload rendering and webhook delivery."""

from __future__ import annotations

import asyncio

from opendevops_core.integrations.slack_webhook import _build_payload, post_investigation

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


def test_build_payload_contains_category_confidence_and_summary():
    payload = _build_payload(SAMPLE_RESULT, "session-1234")
    attachment = payload["attachments"][0]
    blocks = attachment["blocks"]

    assert attachment["color"] == "#e74c3c"
    assert any("RESOURCE_LIMIT" in str(block) for block in blocks)
    assert any("HIGH" in str(block) for block in blocks)
    assert any("Lambda exhausted memory" in str(block) for block in blocks)


def test_post_investigation_sends_payload(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200
        text = "ok"

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

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)

    asyncio.run(
        post_investigation(
            "https://hooks.slack.test/example",
            SAMPLE_RESULT,
            "session-1234",
        )
    )

    assert captured["url"] == "https://hooks.slack.test/example"
    assert "attachments" in captured["json"]
