"""Core configuration.

`CoreSettings` holds every setting the shared agent core reads. Host applications
(the OSS web app, the SaaS product) subclass it to add their own fields, instantiate
it, and register the instance via `configure()`. Core modules read settings through the
module-level `settings` proxy, which always delegates to the configured instance — so a
host app's richer settings object is what core actually sees at runtime.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class CoreSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Primary LLM settings — use LiteLLM model string format:
    #   openrouter/openai/gpt-4o  |  anthropic/claude-3-5-sonnet-20241022
    #   groq/llama3-70b-8192      |  ollama/llama3  |  openai/gpt-4o
    # For custom OpenAI-compatible endpoints set llm_api_base + llm_api_key.
    llm_model: str = "openrouter/openai/gpt-4o"
    llm_api_base: str | None = None  # custom base URL (e.g. http://localhost:11434)
    llm_api_key: str | None = None  # custom API key (falls back to provider env vars)

    # OpenRouter (kept for backward-compat and pricing lookup)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Active cloud provider — selects which provider package supplies tools, context,
    # permission checks, and event/poller loops. One active provider per deployment.
    cloud_provider: Literal["aws", "azure", "gcp"] = "aws"

    aws_region: str = "us-east-1"
    aws_profile: str | None = None

    max_tool_calls: int = 20
    investigation_timeout: int = 120
    log_level: str = "INFO"
    log_console_enabled: bool = True
    log_console_colorize: bool = True

    # Cap tool responses before feeding them back to the LLM.
    # Prevents large CloudWatch / CloudTrail payloads from exhausting the context window.
    # ~40 K chars ≈ 10 K tokens. Set to 0 to disable.
    tool_response_max_chars: int = 40_000

    # Storage backend — controls which DatabaseBackend is used.
    # memory  → no persistence, zero config (default, great for CI / quick testing)
    # sqlite  → local file-based persistence, zero external dependencies
    # postgres → full production persistence
    checkpoint_backend: Literal["memory", "sqlite", "postgres"] = "memory"

    # SQLite file path — only used when checkpoint_backend = "sqlite"
    sqlite_path: str = "./data/agent.db"

    # PostgreSQL connection string — only used when checkpoint_backend = "postgres"
    database_url: str | None = None

    # Conversation summarization — compacts old messages when a session gets long.
    # Fires before each agent call when total message chars exceed the threshold.
    # Set summarization_enabled=false or summarization_threshold_chars=0 to disable.
    summarization_enabled: bool = True
    summarization_threshold_chars: int = 60_000  # ~15 K tokens; trigger compaction above this
    summarization_keep_chars: int = 20_000  # ~5 K tokens of recent messages to keep intact

    # Slack — leave unset to disable notifications
    slack_webhook_url: str | None = None

    # Telegram — leave unset to disable notifications
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    # Proactive polling — set poll_interval_seconds=0 to disable
    poll_interval_seconds: int = 0  # disabled by default
    poll_error_threshold: float = 5.0  # % Lambda error rate that triggers investigation
    poll_reinvestigate_hours: int = 1  # don't re-investigate the same alarm within N hours

    # Event consumer — leave unset to disable
    event_consumer_enabled: bool = False
    sqs_queue_url: str | None = None

    # Reserved for future file-based state; init config is stored in the DB backend.
    data_dir: str = "data"

    # Auto-detect Claude Code CLI and use it as the Anthropic LLM backend.
    # Fires only when LLM_MODEL is not explicitly set and no LLM_API_KEY is present.
    # Set to false to disable auto-detection.
    claude_code_autodetect: bool = True


_settings: CoreSettings | None = None


def configure(settings_instance: CoreSettings) -> None:
    """Register the active settings instance. Host apps call this once at startup."""
    global _settings
    _settings = settings_instance


def get_settings() -> CoreSettings:
    """Return the active settings, lazily defaulting to a bare CoreSettings()."""
    global _settings
    if _settings is None:
        _settings = CoreSettings()
    return _settings


class _SettingsProxy:
    """Delegates attribute access to the configured settings instance at runtime.

    Lets core modules keep `from opendevops_core.config import settings` and read
    `settings.x` unchanged while the host app injects its own settings via configure().
    """

    def __getattr__(self, name: str) -> Any:
        return getattr(get_settings(), name)


settings = _SettingsProxy()
