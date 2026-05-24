"""Cloud provider registry. One active provider per deployment via CLOUD_PROVIDER."""

from __future__ import annotations

from opendevops_core.config import settings
from opendevops_core.providers.base import CloudProvider


def get_active_provider() -> CloudProvider:
    """Return the provider selected by settings.cloud_provider."""
    name = settings.cloud_provider
    if name == "aws":
        from opendevops_core.providers.aws import AwsProvider

        return AwsProvider()
    if name == "azure":
        from opendevops_core.providers.azure import AzureProvider

        return AzureProvider()
    if name == "gcp":
        from opendevops_core.providers.gcp import GcpProvider

        return GcpProvider()
    raise ValueError(f"Unknown CLOUD_PROVIDER: {name!r} (expected aws | azure | gcp)")


__all__ = ["CloudProvider", "get_active_provider"]
