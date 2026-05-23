"""CloudProvider protocol — one implementation per cloud (AWS, Azure, GCP).

A provider bundles everything cloud-specific: the agent tools, deterministic context
collection, permission checks, and the proactive poller / event-consumer loops. The
agent core (LangGraph, LLM, skills, prompts) stays cloud-agnostic and talks only to
the active provider, selected by the CLOUD_PROVIDER setting.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CloudProvider(Protocol):
    name: str  # "aws" | "azure" | "gcp"

    def tools(self) -> list[Any]:
        """Provider-specific agent tools (boto3 / SDK-backed)."""
        ...

    def collect_context(self, event: dict) -> dict:
        """Deterministically pre-fetch resource facts before the LLM runs."""
        ...

    def check_permissions(self, region: str | None) -> dict:
        """Verify credentials have the required read permissions, per service."""
        ...

    async def polling_loop(self) -> None:
        """Proactive anomaly-detection loop (no-op if unsupported)."""
        ...

    async def event_consumer_loop(self) -> None:
        """Event-driven incident-detection loop (no-op if unsupported)."""
        ...
