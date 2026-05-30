"""LLM model picker — runtime override + catalog + preference roundtrip.

These tests pin the contract the Settings → LLM card relies on. If a contributor
adds a new provider to ``_PROVIDER_CATALOG``, regresses the Claude Code catalog,
or breaks the ``resolve_model_and_key(override_*)`` shape, the failures show up
here with descriptive names rather than as opaque UI bugs.

Everything is mocked: no real ``~/.claude``, no real env vars, no real DB.
"""

from __future__ import annotations

import json

import pytest
from opendevops_core.agent.llm import backend
from opendevops_core.agent.llm.detectors import claude_code


# ── Fixtures (mirror test_claude_code_detector.py so the two suites compose) ──


@pytest.fixture
def clean_env(monkeypatch):
    """Strip every LLM-related env var so tests are deterministic on any host."""
    for var in (
        "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "GROQ_API_KEY",
        "GEMINI_API_KEY", "GOOGLE_API_KEY",
        "LLM_MODEL", "LLM_API_BASE", "LLM_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(backend.settings, "openrouter_api_key", "")
    monkeypatch.setattr(backend.settings, "llm_api_base", "")
    monkeypatch.setattr(backend.settings, "llm_api_key", "")


@pytest.fixture
def fake_claude_home(tmp_path, monkeypatch):
    """Redirect the Claude Code detector at a temp dir so we control its 'install' state."""
    settings_path = tmp_path / "settings.json"
    creds_path = tmp_path / ".credentials.json"
    monkeypatch.setattr(claude_code, "_SETTINGS_PATH", settings_path)
    monkeypatch.setattr(claude_code, "_CREDS_PATH", creds_path)
    return settings_path, creds_path


def _claude_installed_and_authed(monkeypatch, fake_claude_home, model_slot="opus"):
    settings_path, creds_path = fake_claude_home
    monkeypatch.setattr(claude_code.shutil, "which", lambda _name: "/usr/bin/claude")
    settings_path.write_text(json.dumps({"model": model_slot}), encoding="utf-8")
    creds_path.write_text(
        json.dumps({"claudeAiOauth": {"accessToken": "sk-ant-oat01-test"}}),
        encoding="utf-8",
    )


# ── available_providers() ────────────────────────────────────────────────────


def test_available_providers_returns_every_catalog_entry(clean_env):
    """All providers in _PROVIDER_CATALOG appear in the result. Adding a new provider
    is one-stop: insert into the catalog dict and this assertion grows automatically."""
    names = {p["name"] for p in backend.available_providers()}
    assert names == set(backend._PROVIDER_CATALOG.keys())


def test_available_providers_marks_unconfigured_with_hint(clean_env):
    """With no env keys set, every API provider is configured=False with a non-empty note
    telling the user which env var to add. Ollama is configured (no key needed)."""
    by_name = {p["name"]: p for p in backend.available_providers()}
    assert by_name["openrouter"]["configured"] is False
    assert "OPENROUTER_API_KEY" in by_name["openrouter"]["note"]
    assert by_name["anthropic"]["configured"] is False
    assert by_name["openai"]["configured"] is False
    assert by_name["gemini"]["configured"] is False
    # Ollama doesn't need a key.
    assert by_name["ollama"]["configured"] is True


def test_available_providers_openrouter_configured_when_key_set(monkeypatch, clean_env):
    monkeypatch.setattr(backend.settings, "openrouter_api_key", "sk-or-test")
    by_name = {p["name"]: p for p in backend.available_providers()}
    assert by_name["openrouter"]["configured"] is True
    # Note is empty when configured.
    assert by_name["openrouter"]["note"] == ""


def test_available_providers_claude_code_lists_multiple_models(
    monkeypatch, fake_claude_home, clean_env
):
    """The Claude Code dropdown surfaces the full catalog (Opus 4.8, Sonnet, Haiku, …),
    not just whatever ~/.claude/settings.json names. Prevents the regression where the
    UI only ever showed one option."""
    _claude_installed_and_authed(monkeypatch, fake_claude_home, model_slot="opus")
    by_name = {p["name"]: p for p in backend.available_providers()}
    cc = by_name["claude_code"]
    assert cc["configured"] is True
    assert len(cc["models"]) >= 5, "Claude Code dropdown must offer multiple models"
    assert "anthropic/claude-opus-4-8" in cc["models"]
    assert "anthropic/claude-sonnet-4-6" in cc["models"]
    assert "anthropic/claude-haiku-4-5-20251001" in cc["models"]


def test_available_providers_claude_code_promotes_user_model_to_top(
    monkeypatch, fake_claude_home, clean_env
):
    """If the user has Sonnet set in ~/.claude/settings.json, Sonnet is the first option
    (so it stays the default selection in the dropdown)."""
    _claude_installed_and_authed(monkeypatch, fake_claude_home, model_slot="sonnet")
    by_name = {p["name"]: p for p in backend.available_providers()}
    assert by_name["claude_code"]["models"][0] == "anthropic/claude-sonnet-4-6"


def test_available_providers_claude_code_unconfigured_when_flag_off(
    monkeypatch, fake_claude_home, clean_env
):
    """CLAUDE_CODE_AUTODETECT=false is the single kill switch — UI grays out Claude Code
    even when the CLI is installed and authenticated."""
    _claude_installed_and_authed(monkeypatch, fake_claude_home)
    monkeypatch.setattr(backend.settings, "claude_code_autodetect", False)
    by_name = {p["name"]: p for p in backend.available_providers()}
    cc = by_name["claude_code"]
    assert cc["configured"] is False
    assert "CLAUDE_CODE_AUTODETECT" in cc["note"]


# ── resolve_model_and_key(override_*) ────────────────────────────────────────


def test_resolve_override_model_uses_explicit_model_and_provider_key(monkeypatch, clean_env):
    """resolve_model_and_key(override_model="anthropic/...") returns that model paired
    with the right env-var key (ANTHROPIC_API_KEY in this case). No detector consulted."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    model, key = backend.resolve_model_and_key(override_model="anthropic/claude-opus-4-8")
    assert model == "anthropic/claude-opus-4-8"
    assert key == "sk-ant-test"


def test_resolve_override_model_openrouter_picks_openrouter_key(monkeypatch, clean_env):
    monkeypatch.setattr(backend.settings, "openrouter_api_key", "sk-or-test")
    model, key = backend.resolve_model_and_key(
        override_model="openrouter/anthropic/claude-opus-4-8"
    )
    assert model == "openrouter/anthropic/claude-opus-4-8"
    assert key == "sk-or-test"


def test_resolve_override_gemini_picks_gemini_key(monkeypatch, clean_env):
    """GOOGLE_API_KEY counts as a Gemini key too — LiteLLM accepts either."""
    monkeypatch.setenv("GOOGLE_API_KEY", "g-test")
    model, key = backend.resolve_model_and_key(override_model="gemini/gemini-2.5-pro")
    assert model == "gemini/gemini-2.5-pro"
    assert key == "g-test"


def test_resolve_claude_code_source_uses_oauth_token(
    monkeypatch, fake_claude_home, clean_env
):
    """override_source='claude_code' resolves to (detector's model, detector's OAuth token).
    The user can call any Claude model with that subscription token."""
    _claude_installed_and_authed(monkeypatch, fake_claude_home, model_slot="opus")
    model, key = backend.resolve_model_and_key(override_source="claude_code")
    assert model == "anthropic/claude-opus-4-8"  # default Opus per detector slot
    assert key == "sk-ant-oat01-test"


def test_resolve_claude_code_source_with_explicit_model_uses_oauth_plus_that_model(
    monkeypatch, fake_claude_home, clean_env
):
    """Picking Claude Code + Sonnet from the UI: OAuth token from the detector, model
    string from the user's pick. This is how the dropdown's multi-model selection works."""
    _claude_installed_and_authed(monkeypatch, fake_claude_home, model_slot="opus")
    model, key = backend.resolve_model_and_key(
        override_source="claude_code",
        override_model="anthropic/claude-sonnet-4-6",
    )
    assert model == "anthropic/claude-sonnet-4-6"
    assert key == "sk-ant-oat01-test"  # still the OAuth token, not an API key


def test_resolve_disabled_claude_code_raises_runtime_error(
    monkeypatch, fake_claude_home, clean_env
):
    """A stale 'claude_code' preference in the DB shouldn't silently bypass the env flag —
    it surfaces a clear error so the user knows to flip the flag or pick another provider."""
    _claude_installed_and_authed(monkeypatch, fake_claude_home)
    monkeypatch.setattr(backend.settings, "claude_code_autodetect", False)
    with pytest.raises(RuntimeError, match="disabled via .env flag"):
        backend.resolve_model_and_key(override_source="claude_code")


def test_resolve_no_override_falls_back_to_env_chain(monkeypatch, clean_env):
    """With no overrides and no env keys, falls through to the default 'not configured'
    info from get_backend_info — the function still returns something callable."""
    # Force-disable the Claude Code detector so the host's real ~/.claude can't satisfy
    # the chain. We're testing the env-fallback branch, not detector behavior.
    monkeypatch.setattr(claude_code.shutil, "which", lambda _name: None)
    model, _key = backend.resolve_model_and_key()
    # Default model from settings.llm_model.
    assert model == backend.settings.llm_model


# ── get_backend_info(pref=...) ───────────────────────────────────────────────


def test_get_backend_info_pref_with_source_reports_picked_in_settings(
    monkeypatch, fake_claude_home, clean_env
):
    """When a preference is saved with source='claude_code', the backend info labels
    the source 'picked in Settings' so the Environment tab UI reflects it."""
    _claude_installed_and_authed(monkeypatch, fake_claude_home)
    info = backend.get_backend_info(pref={"source": "claude_code", "model": ""})
    assert info["source"] == "claude_code"
    assert "picked in Settings" in info["display_name"]


def test_get_backend_info_pref_with_model_only_picks_right_provider(monkeypatch, clean_env):
    """A model-only preference is enough — the provider is inferred from the model string,
    and configured reflects whether the matching env key exists."""
    monkeypatch.setattr(backend.settings, "openrouter_api_key", "sk-or-test")
    info = backend.get_backend_info(
        pref={"source": "", "model": "openrouter/anthropic/claude-opus-4-8"}
    )
    assert info["model"] == "openrouter/anthropic/claude-opus-4-8"
    assert info["provider"] == "openrouter"
    assert info["configured"] is True


def test_get_backend_info_no_pref_falls_back_to_env_default(monkeypatch, clean_env):
    """Without a saved preference, behavior is unchanged from before the picker existed —
    .env values drive get_backend_info()."""
    # Disable the Claude Code detector so a real installation on the test machine doesn't
    # win the priority chain. The branch under test is "env-only, no detectors".
    monkeypatch.setattr(claude_code.shutil, "which", lambda _name: None)
    info = backend.get_backend_info(pref=None)
    # With everything stripped, we land on the 'default / not configured' branch.
    assert info["source"] == "default"


# ── _provider_of() ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("model,expected_provider", [
    ("anthropic/claude-opus-4-8", "anthropic"),
    ("openrouter/anthropic/claude-opus-4-8", "openrouter"),
    ("openai/gpt-4o", "openai"),
    ("groq/llama-3.3-70b-versatile", "groq"),
    ("gemini/gemini-2.5-pro", "gemini"),
    ("ollama/llama3.3", "ollama"),
])
def test_provider_of_classifies_model_string(model, expected_provider):
    """The provider routing used by override_model lookup. Adding a provider means
    extending _provider_of and adding a row here."""
    assert backend._provider_of(model) == expected_provider
