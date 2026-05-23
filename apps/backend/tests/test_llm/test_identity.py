"""System-prompt shaping for subscription OAuth tokens."""

from __future__ import annotations

from opendevops_core.agent.llm.identity import (
    CLAUDE_CODE_IDENTITY,
    is_subscription_token,
    shape_system_content,
)


def test_is_subscription_token():
    assert is_subscription_token("sk-ant-oat01-abc") is True
    assert is_subscription_token("sk-ant-api03-abc") is False
    assert is_subscription_token("sk-or-xxx") is False
    assert is_subscription_token(None) is False
    assert is_subscription_token("") is False


def test_shape_system_content_subscription_returns_two_blocks():
    out = shape_system_content("DEVOPS PROMPT", "sk-ant-oat01-abc")
    assert isinstance(out, list)
    assert out[0] == {"type": "text", "text": CLAUDE_CODE_IDENTITY}
    assert out[1] == {"type": "text", "text": "DEVOPS PROMPT"}


def test_shape_system_content_plain_returns_string():
    assert shape_system_content("P", "sk-or-xxx") == "P"
    assert shape_system_content("P", None) == "P"
    assert shape_system_content("P", "sk-ant-api03-key") == "P"
