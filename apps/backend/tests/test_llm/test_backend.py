"""Backend resolution precedence — the ladder that decides which provider wins.

All detectors are stubbed; no real ~/.claude access, no network, no API spend.
"""

from __future__ import annotations

import pytest
from opendevops_core.agent.llm import backend


class FakeDetector:
    name = "claude_code"
    label = "Claude Code"
    provider = "anthropic"

    def __init__(self, installed=True, resolved=("anthropic/claude-sonnet-4-6", "sk-ant-oat01-x")):
        self._installed = installed
        self._resolved = resolved

    @property
    def enabled(self):
        return True

    def is_installed(self):
        return self._installed

    def resolve(self):
        return self._resolved

    def status(self):
        return {"model": "anthropic/claude-sonnet-4-6", "hint": "log in with claude"}


@pytest.fixture
def clean_env(monkeypatch):
    """Clear provider env vars and set baseline settings (default OpenRouter model, no keys)."""
    for var in (
        "LLM_MODEL", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
        "OPENAI_API_KEY", "GROQ_API_KEY", "COHERE_API_KEY", "MISTRAL_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(backend.settings, "llm_api_base", None)
    monkeypatch.setattr(backend.settings, "llm_api_key", None)
    monkeypatch.setattr(backend.settings, "openrouter_api_key", "")
    monkeypatch.setattr(backend.settings, "llm_model", "openrouter/openai/gpt-4o")
    monkeypatch.setattr(backend.settings, "claude_code_autodetect", True)


def test_claude_code_wins_when_nothing_else_configured(monkeypatch, clean_env):
    monkeypatch.setattr(backend, "ALL_DETECTORS", [FakeDetector()])
    info = backend.get_backend_info()
    assert info["source"] == "claude_code"
    assert info["configured"] is True
    assert info["model"] == "anthropic/claude-sonnet-4-6"


def test_openrouter_key_blocks_claude_code(monkeypatch, clean_env):
    # The precedence that surprised us during testing: OPENROUTER set => Claude Code skipped.
    monkeypatch.setattr(backend.settings, "openrouter_api_key", "sk-or-xxx")
    monkeypatch.setattr(backend, "ALL_DETECTORS", [FakeDetector()])
    assert backend.get_backend_info()["source"] == "openrouter"


def test_anthropic_env_key_wins(monkeypatch, clean_env):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-x")
    monkeypatch.setattr(backend, "ALL_DETECTORS", [FakeDetector()])
    assert backend.get_backend_info()["source"] == "anthropic"


def test_custom_endpoint_wins(monkeypatch, clean_env):
    monkeypatch.setattr(backend.settings, "llm_api_base", "http://localhost:11434")
    assert backend.get_backend_info()["source"] == "custom"


def test_explicit_model_with_openai_key(monkeypatch, clean_env):
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-4o")
    monkeypatch.setattr(backend.settings, "llm_model", "openai/gpt-4o")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    monkeypatch.setattr(backend, "ALL_DETECTORS", [FakeDetector()])
    assert backend.get_backend_info()["source"] == "openai"


def test_installed_but_unauthenticated_detector(monkeypatch, clean_env):
    monkeypatch.setattr(backend, "ALL_DETECTORS", [FakeDetector(installed=True, resolved=None)])
    info = backend.get_backend_info()
    assert info["source"] == "claude_code_no_auth"
    assert info["configured"] is False


def test_unconfigured_default(monkeypatch, clean_env):
    monkeypatch.setattr(backend, "ALL_DETECTORS", [])
    info = backend.get_backend_info()
    assert info["source"] == "default"
    assert info["configured"] is False


def test_resolve_model_and_key_uses_detector(monkeypatch, clean_env):
    monkeypatch.setattr(backend, "ALL_DETECTORS", [FakeDetector()])
    model, key = backend.resolve_model_and_key()
    assert model == "anthropic/claude-sonnet-4-6"
    assert key == "sk-ant-oat01-x"
