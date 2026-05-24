"""Claude Code CLI detector — reuses the local subscription login as an Anthropic backend.

Auth resolution order:
  1. ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN environment variables
  2. Claude Code's OAuth access token (~/.claude/.credentials.json)

LiteLLM (>=1.83) detects ``sk-ant-oat`` tokens and uses Authorization: Bearer + the
OAuth beta header automatically, so the subscription login works with no API key.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from loguru import logger

from opendevops_core.config import settings

_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
_CREDS_PATH = Path.home() / ".claude" / ".credentials.json"

# Claude Code model slot names → LiteLLM model strings.
# Includes both short aliases ("sonnet") and full slot names ("claude-sonnet-4-5").
_MODEL_SLOTS: dict[str, str] = {
    # Short aliases used by Claude Code settings.json
    "sonnet": "anthropic/claude-sonnet-4-6",
    "opus": "anthropic/claude-opus-4-7",
    "haiku": "anthropic/claude-haiku-4-5-20251001",
    # Full slot names
    "claude-opus-4-7": "anthropic/claude-opus-4-7",
    "claude-sonnet-4-6": "anthropic/claude-sonnet-4-6",
    "claude-haiku-4-5": "anthropic/claude-haiku-4-5-20251001",
    "claude-opus-4-5": "anthropic/claude-opus-4-5-20251001",
    "claude-opus-4": "anthropic/claude-opus-4-20251101",
    "claude-sonnet-4-5": "anthropic/claude-sonnet-4-5-20251024",
    "claude-sonnet-4": "anthropic/claude-sonnet-4-20251120",
    "claude-3-5-sonnet-20241022": "anthropic/claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022": "anthropic/claude-3-5-haiku-20241022",
    "claude-3-opus-20240229": "anthropic/claude-3-opus-20240229",
}
_DEFAULT_MODEL = "anthropic/claude-sonnet-4-6"


class ClaudeCodeDetector:
    name = "claude_code"
    label = "Claude Code"
    provider = "anthropic"

    @property
    def enabled(self) -> bool:
        return settings.claude_code_autodetect

    def is_installed(self) -> bool:
        return shutil.which("claude") is not None

    def resolve(self) -> tuple[str, str] | None:
        if not self.is_installed():
            return None
        api_key = self._api_key()
        if not api_key:
            logger.info(
                "claude_code: installed but no auth found — run `claude` to log in or set ANTHROPIC_API_KEY"
            )
            return None
        model = self._model()
        logger.info("claude_code: auto-configuring model={} via {}", model, self._auth_method())
        return model, api_key

    def status(self) -> dict:
        installed = self.is_installed()
        method = self._auth_method() if installed else None
        oauth = self._oauth() if (installed and method == "subscription") else {}
        return {
            "installed": installed,
            "authenticated": bool(method),
            "auth_method": method,  # api_key | auth_token | subscription | None
            "subscription_type": oauth.get("subscriptionType"),
            "token_expired": self._oauth_expired(oauth) if oauth else False,
            "model": self._model() if installed else None,
            "config_path": str(_SETTINGS_PATH) if _SETTINGS_PATH.exists() else None,
            "hint": "Run `claude` to log in, or set ANTHROPIC_API_KEY in .env",
        }

    # ── internals ────────────────────────────────────────────────────────────

    def _model(self) -> str:
        try:
            if _SETTINGS_PATH.exists():
                data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
                slot = data.get("model") or data.get("defaultModel") or ""
                if slot in _MODEL_SLOTS:
                    return _MODEL_SLOTS[slot]
                for key, val in _MODEL_SLOTS.items():
                    if slot.startswith(key):
                        return val
        except Exception:
            pass
        return _DEFAULT_MODEL

    def _oauth(self) -> dict:
        """Return the claudeAiOauth block from Claude Code's credential file, or {}."""
        try:
            if _CREDS_PATH.exists():
                data = json.loads(_CREDS_PATH.read_text(encoding="utf-8"))
                return data.get("claudeAiOauth", {}) or {}
        except Exception:
            pass
        return {}

    def _oauth_expired(self, oauth: dict) -> bool:
        """expiresAt is epoch milliseconds; treat missing as not-expired."""
        expires_at = oauth.get("expiresAt")
        if not expires_at:
            return False
        return int(expires_at) < int(time.time() * 1000)

    def _api_key(self) -> str | None:
        if key := (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
            return key
        return self._oauth().get("accessToken") or None

    def _auth_method(self) -> str | None:
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "api_key"
        if os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            return "auth_token"
        if self._oauth().get("accessToken"):
            return "subscription"
        return None
