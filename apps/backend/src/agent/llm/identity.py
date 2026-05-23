"""Provider-specific system-prompt shaping.

Some backends require the system prompt to be structured a particular way before
they will accept a request. This module centralises that logic so every LLM call
site (agent, summarizer, CLI ask) shapes prompts consistently.
"""

from __future__ import annotations

# Anthropic subscription (OAuth) tokens only accept inference when the first system
# block identifies the caller as Claude Code. Regular API keys do not need this.
CLAUDE_CODE_IDENTITY = "You are Claude Code, Anthropic's official CLI for Claude."


def is_subscription_token(api_key: str | None) -> bool:
    """True when the key is a Claude Code subscription OAuth token (sk-ant-oat…)."""
    return bool(api_key and api_key.startswith("sk-ant-oat"))


def shape_system_content(prompt: str, api_key: str | None) -> str | list[dict]:
    """Shape system-message content for the active backend.

    For Claude subscription OAuth tokens, return two text blocks with the Claude Code
    identity first (required by Anthropic). For everything else, return the plain string.
    """
    if is_subscription_token(api_key):
        return [
            {"type": "text", "text": CLAUDE_CODE_IDENTITY},
            {"type": "text", "text": prompt},
        ]
    return prompt
