from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Primary LLM settings — use LiteLLM model string format:
    #   openrouter/openai/gpt-4o  |  anthropic/claude-3-5-sonnet-20241022
    #   groq/llama3-70b-8192      |  ollama/llama3  |  openai/gpt-4o
    # For custom OpenAI-compatible endpoints set llm_api_base + llm_api_key.
    llm_model: str = "openrouter/openai/gpt-4o"
    llm_api_base: str | None = None   # custom base URL (e.g. http://localhost:11434)
    llm_api_key: str | None = None    # custom API key (falls back to provider env vars)

    # OpenRouter (kept for backward-compat and pricing lookup)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    aws_region: str = "us-east-1"
    aws_profile: str | None = None

    max_tool_calls: int = 20
    investigation_timeout: int = 120
    log_level: str = "INFO"

    # Cap tool responses before feeding them back to the LLM.
    # Prevents large CloudWatch / CloudTrail payloads from exhausting the context window.
    # ~40 K chars ≈ 10 K tokens. Set to 0 to disable.
    tool_response_max_chars: int = 40_000

    # Storage backend: "memory" | "sqlite" | "postgres"
    # memory  → no persistence, zero config (default, great for CI / quick testing)
    # sqlite  → local file-based persistence, zero external dependencies
    # postgres → full production persistence
    checkpoint_backend: str = "memory"

    # SQLite file path — only used when checkpoint_backend = "sqlite"
    sqlite_path: str = "./data/agent.db"

    # PostgreSQL connection string — only used when checkpoint_backend = "postgres"
    database_url: str | None = None

    # Slack — leave unset to disable notifications
    slack_webhook_url: str | None = None

    # Proactive polling — set poll_interval_minutes=0 to disable
    poll_interval_minutes: int = 0          # disabled by default
    poll_error_threshold: float = 5.0       # % Lambda error rate that triggers investigation
    poll_reinvestigate_hours: int = 1       # don't re-investigate the same alarm within N hours


settings = Settings()
