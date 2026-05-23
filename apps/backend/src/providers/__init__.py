"""Cloud provider registry. One active provider per deployment via CLOUD_PROVIDER."""

from __future__ import annotations

from config import settings
from providers.base import CloudProvider


def get_active_provider() -> CloudProvider:
    """Return the provider selected by settings.cloud_provider."""
    name = settings.cloud_provider
    if name == "aws":
        from providers.aws import AwsProvider
        return AwsProvider()
    if name == "azure":
        from providers.azure import AzureProvider
        return AzureProvider()
    if name == "gcp":
        from providers.gcp import GcpProvider
        return GcpProvider()
    raise ValueError(f"Unknown CLOUD_PROVIDER: {name!r} (expected aws | azure | gcp)")


__all__ = ["CloudProvider", "get_active_provider"]
