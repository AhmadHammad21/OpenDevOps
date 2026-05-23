"""Agent core tests: completion parsing, timeout behavior, and failure paths."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from agent import core
from models.agent import Investigation


class _FastAgent:
    async def ainvoke(self, _payload, config=None):
        return {"messages": [SimpleNamespace(content="ok")], "config": config}


class _SlowAgent:
    async def ainvoke(self, _payload, config=None):
        _ = config
        await asyncio.sleep(0.2)
        return {"messages": [SimpleNamespace(content="late")]}


def test_ainvoke_with_timeout_success(monkeypatch):
    monkeypatch.setattr(core, "_agent", _FastAgent())
    monkeypatch.setattr(core.settings, "investigation_timeout", 1)

    result = asyncio.run(core.ainvoke_with_timeout({"messages": []}, {"configurable": {}}))
    assert result["messages"][0].content == "ok"


def test_ainvoke_with_timeout_raises_timeout(monkeypatch):
    monkeypatch.setattr(core, "_agent", _SlowAgent())
    monkeypatch.setattr(core.settings, "investigation_timeout", 0.01)

    with pytest.raises(TimeoutError):
        asyncio.run(core.ainvoke_with_timeout({"messages": []}, {"configurable": {}}))


def test_investigate_completion_path_parses_structured_json(monkeypatch):
    raw_json = {
        "root_cause_category": "RESOURCE_LIMIT",
        "root_cause_summary": "Lambda concurrency exhausted",
        "evidence": ["Throttles spiked"],
        "mitigation_steps": ["Increase reserved concurrency"],
        "validation_steps": ["Watch throttles for 15m"],
        "confidence": "HIGH",
        "services_affected": ["Lambda"],
        "recommended_follow_up": "Add alarm on concurrency",
    }
    payload = "```json\n" + __import__("json").dumps(raw_json) + "\n```"

    def fake_invoke(_input, _config):
        return {"messages": [SimpleNamespace(content=payload)]}

    monkeypatch.setattr(core, "ensure_agent_initialized", lambda: None)
    monkeypatch.setattr(core, "invoke_with_timeout", fake_invoke)

    result = core.InvestigationAgent().investigate(Investigation(description="high Lambda errors"))
    assert result.root_cause_summary == "Lambda concurrency exhausted"
    assert result.confidence.value == "HIGH"
    assert result.root_cause_category.value == "RESOURCE_LIMIT"


def test_investigate_failure_path_propagates_agent_error(monkeypatch):
    def failing_invoke(_input, _config):
        raise RuntimeError("recursion limit reached")

    monkeypatch.setattr(core, "ensure_agent_initialized", lambda: None)
    monkeypatch.setattr(core, "invoke_with_timeout", failing_invoke)

    with pytest.raises(RuntimeError, match="recursion"):
        core.InvestigationAgent().investigate(Investigation(description="check recursion failure"))
