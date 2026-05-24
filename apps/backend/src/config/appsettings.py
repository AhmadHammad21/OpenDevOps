from opendevops_core.config import CoreSettings, configure


class Settings(CoreSettings):
    """OSS web-app settings — core fields plus web/auth-only fields."""

    # Auth — leave jwt_secret unset to disable auth (dev / memory-backend mode)
    jwt_secret: str | None = None
    jwt_expire_minutes: int = 1440  # 24 hours


settings = Settings()

# Register this instance so opendevops_core reads the app's settings at runtime.
configure(settings)
