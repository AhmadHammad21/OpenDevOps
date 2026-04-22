from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    aws_region: str = "us-east-1"
    aws_profile: str | None = None

    max_tool_calls: int = 20
    investigation_timeout: int = 120
    log_level: str = "INFO"


settings = Settings()
