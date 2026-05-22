"""Azure cloud provider — stub. Not yet implemented.

To implement: add tools under providers/azure/tools/ (Azure Monitor, App Insights,
Functions, VMs…), a context collector, permission checks, and event ingestion
(Event Grid / Service Bus), then fill in the methods below.
"""

from __future__ import annotations

from typing import Any

from loguru import logger


class AzureProvider:
    name = "azure"

    def tools(self) -> list[Any]:
        logger.warning("Azure provider not yet implemented — no cloud tools loaded")
        return []

    def collect_context(self, event: dict) -> dict:
        return {}

    def check_permissions(self, region: str | None) -> dict:
        return {}

    async def polling_loop(self) -> None:
        return

    async def event_consumer_loop(self) -> None:
        return


__all__ = ["AzureProvider"]
