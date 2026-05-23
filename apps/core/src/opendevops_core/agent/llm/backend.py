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


def resolve_model_and_key() -> tuple[str, str | None]:
    """Return (litellm_model_string, api_key_or_None) for ChatLiteLLM initialisation.

    Called from init_agent() in core.py and other LLM call sites.
    """
    info = get_backend_info()

    # If a CLI detector supplied the backend, use its resolved (model, key)
    for det in ALL_DETECTORS:
        if info["source"] == det.name:
            resolved = det.resolve()
            if resolved:
                return resolved

    return info["model"], (settings.llm_api_key or None)
