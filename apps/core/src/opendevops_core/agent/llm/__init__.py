"""LLM backend resolution and provider detection.

Public API:
  - resolve_model_and_key(): (model, api_key) for ChatLiteLLM initialisation
  - get_backend_info():      a description of the active backend for the UI
  - shape_system_content():  provider-specific system-prompt shaping
"""

from opendevops_core.agent.llm.backend import (
    LlmBackendInfo,
    ProviderInfo,
    available_providers,
    get_backend_info,
    resolve_model_and_key,
)
from opendevops_core.agent.llm.identity import (
    CLAUDE_CODE_IDENTITY,
    is_subscription_token,
    shape_system_content,
)
from opendevops_core.agent.llm.preference import (
    LlmPreference,
    load_llm_preference,
    save_llm_preference,
)

__all__ = [
    "LlmBackendInfo",
    "ProviderInfo",
    "available_providers",
    "get_backend_info",
    "resolve_model_and_key",
    "CLAUDE_CODE_IDENTITY",
    "is_subscription_token",
    "shape_system_content",
    "LlmPreference",
    "load_llm_preference",
    "save_llm_preference",
]
