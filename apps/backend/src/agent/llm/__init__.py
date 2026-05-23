"""LLM backend resolution and provider detection.

Public API:
  - resolve_model_and_key(): (model, api_key) for ChatLiteLLM initialisation
  - get_backend_info():      a description of the active backend for the UI
  - shape_system_content():  provider-specific system-prompt shaping
"""

from agent.llm.backend import LlmBackendInfo, get_backend_info, resolve_model_and_key
from agent.llm.identity import (
    CLAUDE_CODE_IDENTITY,
    is_subscription_token,
    shape_system_content,
)

__all__ = [
    "LlmBackendInfo",
    "get_backend_info",
    "resolve_model_and_key",
    "CLAUDE_CODE_IDENTITY",
    "is_subscription_token",
    "shape_system_content",
]
