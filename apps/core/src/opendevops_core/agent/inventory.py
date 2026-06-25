"""Tool / permission inventory — a trust artifact, built by introspection.

Everything here is sourced from the *live* code objects (the registered ``ALL_TOOLS``,
the bash-tool allowlist constants, the AWS permission-probe table, and each provider's
``tools()``) so the published inventory can never drift from what the agent can actually
do. There is no hand-maintained duplicate list — add a tool / verb / probe in its own
module and it shows up here automatically.

Consumed by the read-only ``/api/inventory`` endpoint and the documentation generator
(``apps/backend/scripts/gen_tool_inventory.py``).
"""

from __future__ import annotations

import functools
import inspect
import types
from typing import Any


def _type_str(annotation: Any) -> str:
    """Render a parameter/return annotation as a readable string, tolerating both real
    type objects and PEP-563 string annotations (``from __future__ import annotations``)."""
    if annotation is inspect.Signature.empty or annotation is inspect.Parameter.empty:
        return "any"
    if isinstance(annotation, str):
        return annotation
    # Unions (``str | None``) and generics (``list[str]``) read best via str().
    if isinstance(annotation, types.UnionType) or getattr(annotation, "__args__", None) is not None:
        return str(annotation).replace("typing.", "")
    name = getattr(annotation, "__name__", None)
    if name:
        return name
    return str(annotation).replace("typing.", "")


def _first_paragraph(doc: str | None) -> str:
    """First paragraph of a docstring (blank-line delimited), whitespace-collapsed."""
    if not doc:
        return ""
    para: list[str] = []
    for line in inspect.cleandoc(doc).splitlines():
        if not line.strip():
            break
        para.append(line.strip())
    return " ".join(para)


def describe_tool(fn: Any) -> dict[str, Any]:
    """Introspect a single tool function into {name, module, description, parameters, returns}.

    ``inspect.signature`` follows ``__wrapped__``, so cached tools (``@tool_cached``) are
    introspected as their underlying function."""
    sig = inspect.signature(fn)
    params: list[dict[str, Any]] = []
    for name, p in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        required = p.default is inspect.Parameter.empty
        params.append(
            {
                "name": name,
                "type": _type_str(p.annotation),
                "required": required,
                "default": None if required else p.default,
            }
        )
    return {
        "name": getattr(fn, "__name__", repr(fn)),
        "module": getattr(fn, "__module__", ""),
        "description": _first_paragraph(getattr(fn, "__doc__", None)),
        "parameters": params,
        "returns": _type_str(sig.return_annotation),
    }


def _bash_allowlist() -> dict[str, Any]:
    """The read-only command allowlist, sourced from the bash-tool constants."""
    from opendevops_core.tools import bash_tool as bt

    return {
        "aws": {
            "readonly_verbs": sorted(bt._AWS_READONLY_VERBS),
            "blocked_global_flags": sorted(bt._AWS_BLOCKED_GLOBAL_FLAGS),
            "note": "aws <service> <operation> where the operation starts with a read-only verb",
        },
        "az": {
            "readonly_verbs": sorted(bt._AZ_READONLY_VERBS),
            "note": "az <group...> <verb> where the trailing verb is read-only",
        },
        "kubectl": {"subcommands": sorted(bt._KUBECTL_SUBCOMMANDS)},
        "docker": {"subcommands": sorted(bt._DOCKER_SUBCOMMANDS)},
        "timeout_seconds": bt._TIMEOUT,
        "max_output_chars": bt._MAX_OUTPUT,
        "shell_chaining": "blocked",
    }


def _permission_matrix() -> list[dict[str, str]]:
    """The per-service AWS read-permission probe, sourced from the probe table."""
    from opendevops_core.providers.aws.permissions import PERMISSION_PROBES

    return [
        {"service": label, "boto3_service": svc, "operation": op}
        for label, svc, op, _kwargs in PERMISSION_PROBES
    ]


def _provider_capabilities() -> list[dict[str, Any]]:
    """Honest, introspected per-provider capability tiers — the structured-tool count is
    read straight from each provider's ``tools()`` (AWS = full set; Azure / GCP = none)."""
    from opendevops_core.config import settings
    from opendevops_core.providers.aws import AwsProvider
    from opendevops_core.providers.azure import AzureProvider
    from opendevops_core.providers.gcp import GcpProvider

    active = settings.cloud_provider
    rows: list[dict[str, Any]] = []
    # structured_tools is introspected from each provider's tools(), but cli_access and
    # event_driven_and_polling are manually maintained booleans — those capabilities aren't
    # trivially introspectable, so update them by hand if a provider gains CLI access or an
    # event/polling loop.
    for provider, cli, event_driven in (
        (AwsProvider(), True, True),
        (AzureProvider(), True, False),
        (GcpProvider(), False, False),
    ):
        rows.append(
            {
                "name": provider.name,
                "active": provider.name == active,
                "structured_tools": len(provider.tools()),
                "cli_access": cli,
                "event_driven_and_polling": event_driven,
            }
        )
    return rows


@functools.lru_cache(maxsize=1)
def build_inventory() -> dict[str, Any]:
    """Assemble the full, introspected tool/permission inventory.

    Memoized for the process lifetime: every source (``ALL_TOOLS``, the bash allowlist
    constants, ``PERMISSION_PROBES``, the active provider, and each provider's ``tools()``)
    is fixed at import/config time, so the inventory is immutable per process. Caching also
    keeps the Azure/GCP ``tools()`` stub warnings from firing on every ``/api/inventory`` hit."""
    from opendevops_core.agent.core import ALL_TOOLS
    from opendevops_core.providers import get_active_provider

    return {
        "active_provider": get_active_provider().name,
        "tool_count": len(ALL_TOOLS),
        "tools": [describe_tool(t) for t in ALL_TOOLS],
        "bash_allowlist": _bash_allowlist(),
        "aws_permission_matrix": _permission_matrix(),
        "providers": _provider_capabilities(),
    }


__all__ = ["build_inventory", "describe_tool"]
