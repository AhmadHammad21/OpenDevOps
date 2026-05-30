"""Resolve and describe the active LLM backend from all available configuration sources.

Priority order (first match wins):
  1. LLM_API_BASE set                          → custom endpoint
  2. ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN  → anthropic (direct)
  3. OPENROUTER_API_KEY + openrouter model     → openrouter
  4. Other explicit provider key + LLM_MODEL   → that provider
  5. Installed CLI detector (e.g. Claude Code) → subscription login
  6. Nothing                                   → unconfigured
"""

from __future__ import annotations

import os
import re
from typing import TypedDict

from opendevops_core.agent.llm.detectors import ALL_DETECTORS
from opendevops_core.config import settings

_DATE_SUFFIX = re.compile(r"-\d{8}$")


class LlmBackendInfo(TypedDict):
    source: str  # claude_code | anthropic | openrouter | openai | groq | custom | default
    model: str  # active LiteLLM model string
    display_name: str  # human-readable source name shown in the UI
    provider: str  # anthropic | openai | openrouter | groq | ollama | custom
    configured: bool  # True when valid auth is present
    detail: str  # friendly model name or setup hint


def _strip_date(model: str) -> str:
    return _DATE_SUFFIX.sub("", model.split("/")[-1])


def _provider_of(model: str) -> str:
    if model.startswith("anthropic/"):
        return "anthropic"
    if "openrouter" in model:
        return "openrouter"
    if model.startswith("openai/") or "gpt" in model:
        return "openai"
    if model.startswith("groq/"):
        return "groq"
    if model.startswith("ollama/"):
        return "ollama"
    return "custom"


def _detector_backend() -> LlmBackendInfo | None:
    """Consult CLI detectors in registry order; return the first installed one."""
    for det in ALL_DETECTORS:
        if not det.enabled or not det.is_installed():
            continue
        resolved = det.resolve()
        if resolved:
            model, _ = resolved
            return LlmBackendInfo(
                source=det.name,
                model=model,
                display_name=f"{det.label} (auto-detected)",
                provider=det.provider,
                configured=True,
                detail=_strip_date(model),
            )
        st = det.status()
        return LlmBackendInfo(
            source=f"{det.name}_no_auth",
            model=st.get("model") or settings.llm_model,
            display_name=f"{det.label} (not authenticated)",
            provider=det.provider,
            configured=False,
            detail=st.get("hint") or "Authenticate the CLI or set an API key",
        )
    return None


def get_backend_info() -> LlmBackendInfo:
    """Return a description of the active LLM backend for /api/settings and /api/init/status."""
    model = settings.llm_model
    api_base = settings.llm_api_base or None
    explicit_model = bool(os.environ.get("LLM_MODEL"))

    # Custom endpoint always takes precedence
    if api_base:
        return LlmBackendInfo(
            source="custom",
            model=model,
            display_name="Custom endpoint",
            provider="custom",
            configured=True,
            detail=api_base,
        )

    # Anthropic direct (env key)
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        source, label = "anthropic", "Anthropic API key"
        if explicit_model and "anthropic" not in model:
            source = _provider_of(model)
            label = source.title() + " (via .env)"
        return LlmBackendInfo(
            source=source,
            model=model,
            display_name=label,
            provider=_provider_of(model),
            configured=True,
            detail=_strip_date(model),
        )

    # OpenRouter key
    if settings.openrouter_api_key and "openrouter" in model:
        return LlmBackendInfo(
            source="openrouter",
            model=model,
            display_name="OpenRouter",
            provider="openrouter",
            configured=True,
            detail=_strip_date(model),
        )

    # Any other explicit provider key (OPENAI_API_KEY, GROQ_API_KEY, …)
    if explicit_model:
        provider = _provider_of(model)
        has_key = any(
            os.environ.get(k)
            for k in ("OPENAI_API_KEY", "GROQ_API_KEY", "COHERE_API_KEY", "MISTRAL_API_KEY")
        )
        if has_key:
            return LlmBackendInfo(
                source=provider,
                model=model,
                display_name=provider.title() + " (via .env)",
                provider=provider,
                configured=True,
                detail=_strip_date(model),
            )

    # Installed CLI detector (subscription login)
    detected = _detector_backend()
    if detected:
        return detected

    return LlmBackendInfo(
        source="default",
        model=model,
        display_name="Not configured",
        provider=_provider_of(model),
        configured=False,
        detail="Set LLM_MODEL and an API key in .env, or install a supported CLI (e.g. Claude Code)",
    )


def resolve_model_and_key(
    override_source: str | None = None,
    override_model: str | None = None,
) -> tuple[str, str | None]:
    """Return (litellm_model_string, api_key_or_None) for ChatLiteLLM initialisation.

    With no arguments, behaves as before: walk the env/detector priority chain and pick the
    first match. With ``override_source`` and/or ``override_model`` provided (typically from
    the UI's ``app_config["llm_preference"]`` row), bypass the default chain and use the
    user-selected provider and model.

      * ``override_source == "claude_code"`` (or any detector name) — run that detector's
        resolve() and return its (model, key). Lets the user explicitly opt in to the
        subscription login from the UI, independent of CLAUDE_CODE_AUTODETECT.
      * ``override_model`` set, no source — look up the api key for the provider implied
        by the model string (anthropic/* -> ANTHROPIC_API_KEY, openrouter/* -> OPENROUTER_API_KEY, ...).
    """
    if override_source:
        for det in ALL_DETECTORS:
            if det.name == override_source:
                resolved = det.resolve()
                if resolved:
                    return resolved
                # detector enabled in UI but no auth available -> surface a useful error
                raise RuntimeError(
                    f"{det.label}: selected in Settings but not authenticated. {det.status().get('hint', '')}"
                )

    if override_model:
        provider = _provider_of(override_model)
        key = _api_key_for_provider(provider)
        return override_model, key

    info = get_backend_info()

    # If a CLI detector supplied the backend, use its resolved (model, key)
    for det in ALL_DETECTORS:
        if info["source"] == det.name:
            resolved = det.resolve()
            if resolved:
                return resolved

    return info["model"], (settings.llm_api_key or None)


def _api_key_for_provider(provider: str) -> str | None:
    """Return the API key env var (or settings field) associated with a provider name."""
    if provider == "anthropic":
        return os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if provider == "openrouter":
        return settings.openrouter_api_key or os.environ.get("OPENROUTER_API_KEY")
    if provider == "openai":
        return os.environ.get("OPENAI_API_KEY")
    if provider == "groq":
        return os.environ.get("GROQ_API_KEY")
    if provider == "ollama":
        return None  # local server, no key
    return settings.llm_api_key or None


# A small curated catalog of models per provider, shown in the Settings UI dropdown.
# Custom models still work via .env LLM_MODEL — this is just for the picker convenience.
_PROVIDER_CATALOG: dict[str, tuple[str, str, list[str]]] = {
    # source_key: (label, requires_check_key_env_var_or_marker, models)
    "claude_code":  ("Claude Code (subscription)", "CLAUDE_CODE",   []),  # models from ~/.claude
    "anthropic":    ("Anthropic API",              "ANTHROPIC",     [
        "anthropic/claude-opus-4-7",
        "anthropic/claude-sonnet-4-6",
        "anthropic/claude-haiku-4-5-20251001",
    ]),
    "openrouter":   ("OpenRouter",                 "OPENROUTER",    [
        "openrouter/anthropic/claude-opus-4-7",
        "openrouter/anthropic/claude-sonnet-4-6",
        "openrouter/openai/gpt-4o",
        "openrouter/openai/gpt-4o-mini",
        "openrouter/google/gemini-2.5-pro",
    ]),
    "openai":       ("OpenAI",                     "OPENAI",        [
        "openai/gpt-4o",
        "openai/gpt-4o-mini",
        "openai/gpt-4-turbo",
    ]),
    "groq":         ("Groq",                       "GROQ",          [
        "groq/llama-3.3-70b-versatile",
        "groq/llama-3.1-8b-instant",
    ]),
    "ollama":       ("Ollama (local)",             "OLLAMA",        [
        "ollama/llama3.3",
        "ollama/qwen2.5-coder",
    ]),
}


class ProviderInfo(TypedDict):
    name: str             # source key — "claude_code" | "anthropic" | "openrouter" | ...
    label: str            # human-readable
    configured: bool      # True if creds are available for this provider
    models: list[str]     # curated picks; Claude Code is empty (auto-detected)
    note: str             # hint shown in UI when unconfigured


def available_providers() -> list[ProviderInfo]:
    """Describe every provider the Settings UI can offer, with a ``configured`` flag.

    The UI greys out providers whose credentials are not present in ``.env`` (or whose CLI
    detector is not installed/authenticated). For Claude Code, ``configured`` reflects
    whether the local subscription login is usable right now.
    """
    out: list[ProviderInfo] = []
    for source, (label, marker, models) in _PROVIDER_CATALOG.items():
        if source == "claude_code":
            # Defer to the detector for the actual status.
            det = next((d for d in ALL_DETECTORS if d.name == "claude_code"), None)
            st = det.status() if det else {}
            configured = bool(st.get("installed") and st.get("authenticated"))
            note = (
                "Run `claude` to log in" if det and st.get("installed") and not st.get("authenticated")
                else "Install Claude Code to enable" if det and not st.get("installed")
                else ""
            )
            # When Claude Code is configured, surface the model the user picked there.
            cc_model = st.get("model")
            out.append(ProviderInfo(
                name=source,
                label=label,
                configured=configured,
                models=[cc_model] if cc_model else [],
                note=note,
            ))
            continue

        if marker == "ANTHROPIC":
            configured = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
            note = "Set ANTHROPIC_API_KEY in .env"
        elif marker == "OPENROUTER":
            configured = bool(settings.openrouter_api_key or os.environ.get("OPENROUTER_API_KEY"))
            note = "Set OPENROUTER_API_KEY in .env"
        elif marker == "OPENAI":
            configured = bool(os.environ.get("OPENAI_API_KEY"))
            note = "Set OPENAI_API_KEY in .env"
        elif marker == "GROQ":
            configured = bool(os.environ.get("GROQ_API_KEY"))
            note = "Set GROQ_API_KEY in .env"
        elif marker == "OLLAMA":
            # No key needed; just having an LLM_API_BASE pointing at Ollama is enough.
            # We don't probe the server here — show as available; resolution failure surfaces on use.
            configured = True
            note = "Configure LLM_API_BASE for non-default Ollama endpoints"
        else:
            configured = False
            note = ""

        out.append(ProviderInfo(
            name=source,
            label=label,
            configured=configured,
            models=list(models),
            note=note if not configured else "",
        ))
    return out
