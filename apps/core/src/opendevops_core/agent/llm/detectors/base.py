"""Detector protocol for CLI-based LLM backends.

A detector recognises a locally-installed CLI tool (Claude Code, Gemini CLI, Codex…)
and reuses its existing login as an LLM backend — no API key required. New providers
are added by implementing this protocol and registering the class in ``__init__.py``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LlmDetector(Protocol):
    name: str  # stable id used as the backend `source`, e.g. "claude_code"
    label: str  # brand name shown in the UI, e.g. "Claude Code"
    provider: str  # litellm provider family, e.g. "anthropic"

    @property
    def enabled(self) -> bool:
        """Whether auto-detection for this provider is turned on (via settings)."""
        ...

    def is_installed(self) -> bool:
        """True if the CLI tool is present on this machine."""
        ...

    def resolve(self) -> tuple[str, str] | None:
        """Return (litellm_model, api_key) when installed AND authenticated, else None."""
        ...

    def status(self) -> dict:
        """Rich status for the settings / init UI (installed, authenticated, model, hint…)."""
        ...
