"""ClaudeCodeDetector — fully mocked: no real ~/.claude access, no network, no API spend."""

from __future__ import annotations

import json
import time

import pytest
from opendevops_core.agent.llm.detectors import claude_code
from opendevops_core.agent.llm.detectors.claude_code import ClaudeCodeDetector


@pytest.fixture
def clean_anthropic_env(monkeypatch):
    """Remove env auth so tests are deterministic regardless of the host machine."""
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def fake_claude_home(tmp_path, monkeypatch):
    """Point the detector at temp credential/settings files instead of the real ~/.claude."""
    settings_path = tmp_path / "settings.json"
    creds_path = tmp_path / ".credentials.json"
    monkeypatch.setattr(claude_code, "_SETTINGS_PATH", settings_path)
    monkeypatch.setattr(claude_code, "_CREDS_PATH", creds_path)
    return settings_path, creds_path


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def _installed(monkeypatch):
    monkeypatch.setattr(claude_code.shutil, "which", lambda _name: "/usr/bin/claude")


def test_not_installed(monkeypatch, fake_claude_home):
    monkeypatch.setattr(claude_code.shutil, "which", lambda _name: None)
    det = ClaudeCodeDetector()
    assert det.is_installed() is False
    assert det.resolve() is None
    st = det.status()
    assert st["installed"] is False
    assert st["authenticated"] is False


def test_installed_subscription_resolves(monkeypatch, fake_claude_home, clean_anthropic_env):
    settings_path, creds_path = fake_claude_home
    _installed(monkeypatch)
    _write(settings_path, {"model": "sonnet"})
    _write(creds_path, {"claudeAiOauth": {
        "accessToken": "sk-ant-oat01-xyz",
        "expiresAt": int(time.time() * 1000) + 3_600_000,
        "subscriptionType": "pro",
    }})
    det = ClaudeCodeDetector()
    model, key = det.resolve()
    assert model == "anthropic/claude-sonnet-4-6"
    assert key == "sk-ant-oat01-xyz"
    st = det.status()
    assert st["auth_method"] == "subscription"
    assert st["subscription_type"] == "pro"
    assert st["token_expired"] is False


@pytest.mark.parametrize("slot,expected", [
    ("sonnet", "anthropic/claude-sonnet-4-6"),
    ("opus", "anthropic/claude-opus-4-8"),     # latest Opus
    ("haiku", "anthropic/claude-haiku-4-5-20251001"),
    ("some-future-model", "anthropic/claude-opus-4-8"),  # unknown slot → default (latest Opus)
])
def test_model_slot_mapping(monkeypatch, fake_claude_home, clean_anthropic_env, slot, expected):
    settings_path, creds_path = fake_claude_home
    _installed(monkeypatch)
    _write(settings_path, {"model": slot})
    _write(creds_path, {"claudeAiOauth": {"accessToken": "sk-ant-oat01-xyz"}})
    assert ClaudeCodeDetector().resolve()[0] == expected


def test_env_key_takes_precedence_over_subscription(monkeypatch, fake_claude_home):
    settings_path, creds_path = fake_claude_home
    _installed(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-realkey")
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    _write(settings_path, {"model": "sonnet"})
    _write(creds_path, {"claudeAiOauth": {"accessToken": "sk-ant-oat01-xyz"}})
    det = ClaudeCodeDetector()
    _model, key = det.resolve()
    assert key == "sk-ant-api03-realkey"
    assert det.status()["auth_method"] == "api_key"


def test_installed_but_no_auth(monkeypatch, fake_claude_home, clean_anthropic_env):
    settings_path, _creds_path = fake_claude_home
    _installed(monkeypatch)
    _write(settings_path, {"model": "sonnet"})  # no creds file, no env
    det = ClaudeCodeDetector()
    assert det.resolve() is None
    st = det.status()
    assert st["installed"] is True
    assert st["authenticated"] is False
    assert st["auth_method"] is None


def test_expired_token_flag(monkeypatch, fake_claude_home, clean_anthropic_env):
    settings_path, creds_path = fake_claude_home
    _installed(monkeypatch)
    _write(settings_path, {"model": "sonnet"})
    _write(creds_path, {"claudeAiOauth": {
        "accessToken": "sk-ant-oat01-xyz",
        "expiresAt": int(time.time() * 1000) - 1000,  # already expired
        "subscriptionType": "pro",
    }})
    assert ClaudeCodeDetector().status()["token_expired"] is True
