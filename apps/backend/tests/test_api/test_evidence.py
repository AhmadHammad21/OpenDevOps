"""Tests for GET /api/sessions/{id}/evidence — the replayable evidence pack endpoint."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("CHECKPOINT_BACKEND", "memory")
os.environ.setdefault("LLM_MODEL", "openrouter/anthropic/claude-3.5-sonnet")
os.environ.setdefault("LLM_API_KEY", "test-key")


async def _seed_investigation(session_id: str) -> None:
    """Persist a session with supporting tool calls + a submit_investigation conclusion."""
    from opendevops_core.agent.db import db

    await db.upsert_session(session_id, "test-model", "us-east-1", title="Lambda throttling")
    msg_id = await db.save_message(session_id, "assistant", "Investigation complete.")

    await db.save_tool_call(
        session_id,
        msg_id,
        "get_metric_data",
        {
            "namespace": "AWS/Lambda",
            "metric": "Throttles",
            "dimensions": [{"Name": "FunctionName", "Value": "payment-fn"}],
        },
        {"count": 1, "datapoints": [{"timestamp": "t", "value": 120}]},
    )
    await db.save_tool_call(
        session_id,
        msg_id,
        "query_logs_insights",
        {
            "log_group": "/aws/lambda/payment-fn",
            "query": "fields @timestamp, @message | filter @message like /Throttl/",
        },
        {"results": []},
    )
    await db.save_tool_call(
        session_id,
        msg_id,
        "run_bash_command",
        {"command": "az monitor metrics list --resource payment-fn"},
        {"stdout": "ok"},
    )
    await db.save_tool_call(
        session_id,
        msg_id,
        "submit_investigation",
        {
            "root_cause_category": "RESOURCE_LIMIT",
            "root_cause_summary": "payment-fn hit its concurrency limit",
            "hypotheses": [
                {
                    "hypothesis": "Concurrency limit reached on payment-fn",
                    "evidence": ["Throttles metric on payment-fn spiked to 120"],
                    "confidence": "HIGH",
                },
                {
                    "hypothesis": "Downstream dependency slow",
                    "evidence": ["No corroborating evidence found"],
                    "confidence": "LOW",
                },
            ],
            "evidence": ["Throttles metric on payment-fn spiked to 120"],
            "confidence": "HIGH",
        },
        {},
    )


@pytest.mark.asyncio
async def test_evidence_grouped_per_hypothesis_and_linked():
    from httpx import ASGITransport, AsyncClient

    from api.app import app

    session_id = "evid-test-grouped-1"
    await _seed_investigation(session_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(f"/api/sessions/{session_id}/evidence")

    assert r.status_code == 200
    pack = r.json()

    assert pack["has_conclusion"] is True
    assert pack["aws_region"] == "us-east-1"
    assert pack["root_cause_category"] == "RESOURCE_LIMIT"

    # Two ranked hypotheses, most likely first.
    assert [h["hypothesis"] for h in pack["hypotheses"]] == [
        "Concurrency limit reached on payment-fn",
        "Downstream dependency slow",
    ]

    # submit_investigation is the conclusion, never a replay entry.
    assert all(tc["tool"] != "submit_investigation" for tc in pack["tool_calls"])
    assert len(pack["tool_calls"]) == 3

    # The top hypothesis's evidence links to the get_metric_data call that produced it.
    top_ev = pack["hypotheses"][0]["evidence"][0]
    linked_id = top_ev["tool_call_id"]
    assert linked_id is not None
    linked = next(tc for tc in pack["tool_calls"] if tc["id"] == linked_id)
    assert linked["tool"] == "get_metric_data"


@pytest.mark.asyncio
async def test_evidence_exposes_command_and_console_deeplink():
    from httpx import ASGITransport, AsyncClient

    from api.app import app

    session_id = "evid-test-deeplink-2"
    await _seed_investigation(session_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(f"/api/sessions/{session_id}/evidence")

    pack = r.json()
    by_tool = {tc["tool"]: tc for tc in pack["tool_calls"]}

    # Logs Insights: exact query verbatim + a deterministic console deeplink.
    insights = by_tool["query_logs_insights"]
    assert insights["command"] == "fields @timestamp, @message | filter @message like /Throttl/"
    assert insights["console_url"].startswith("https://us-east-1.console.aws.amazon.com/cloudwatch")
    assert "logs-insights" in insights["console_url"]

    # Azure / bash: the literal command is surfaced, no console deeplink.
    bash = by_tool["run_bash_command"]
    assert bash["command"] == "az monitor metrics list --resource payment-fn"
    assert bash["console_url"] is None


@pytest.mark.asyncio
async def test_evidence_unknown_session_is_empty():
    from httpx import ASGITransport, AsyncClient

    from api.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/sessions/no-such-session/evidence")

    assert r.status_code == 200
    pack = r.json()
    assert pack["has_conclusion"] is False
    assert pack["hypotheses"] == []
    assert pack["tool_calls"] == []
