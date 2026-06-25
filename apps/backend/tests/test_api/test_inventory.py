"""Tests for GET /api/inventory — the published tool/permission inventory.

The inventory is a trust artifact: it must reflect the *live* code (``ALL_TOOLS``, the
bash allowlist, the AWS permission probes) with no hand-maintained duplicate that could
drift. These tests assert exactly that correspondence.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("CHECKPOINT_BACKEND", "memory")
os.environ.setdefault("LLM_MODEL", "openrouter/anthropic/claude-3.5-sonnet")
os.environ.setdefault("LLM_API_KEY", "test-key")


@pytest.mark.asyncio
async def test_inventory_reflects_all_tools():
    """Every registered tool appears in the endpoint, by name, with no extras."""
    from httpx import ASGITransport, AsyncClient
    from opendevops_core.agent.core import ALL_TOOLS

    from api.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/inventory")

    assert r.status_code == 200
    data = r.json()

    expected = {t.__name__ for t in ALL_TOOLS}
    returned = {t["name"] for t in data["tools"]}
    assert returned == expected
    assert data["tool_count"] == len(ALL_TOOLS)


@pytest.mark.asyncio
async def test_inventory_tool_parameters_introspected():
    """Parameters are introspected from signatures, not hand-written."""
    from httpx import ASGITransport, AsyncClient

    from api.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        data = (await client.get("/api/inventory")).json()

    tools = {t["name"]: t for t in data["tools"]}
    # get_alarm_history(alarm_name: str, hours: int = 24)
    hist = tools["get_alarm_history"]
    params = {p["name"]: p for p in hist["parameters"]}
    assert params["alarm_name"]["required"] is True
    assert params["hours"]["required"] is False
    assert params["hours"]["default"] == 24


@pytest.mark.asyncio
async def test_inventory_bash_allowlist_matches_source():
    """The published allowlist is sourced from the bash-tool constants."""
    from httpx import ASGITransport, AsyncClient
    from opendevops_core.tools import bash_tool as bt

    from api.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        data = (await client.get("/api/inventory")).json()

    allow = data["bash_allowlist"]
    assert set(allow["aws"]["readonly_verbs"]) == set(bt._AWS_READONLY_VERBS)
    assert set(allow["az"]["readonly_verbs"]) == set(bt._AZ_READONLY_VERBS)
    assert set(allow["kubectl"]["subcommands"]) == set(bt._KUBECTL_SUBCOMMANDS)
    assert set(allow["docker"]["subcommands"]) == set(bt._DOCKER_SUBCOMMANDS)


@pytest.mark.asyncio
async def test_inventory_permission_matrix_matches_probes():
    """The permission matrix is sourced from PERMISSION_PROBES."""
    from httpx import ASGITransport, AsyncClient
    from opendevops_core.providers.aws.permissions import PERMISSION_PROBES

    from api.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        data = (await client.get("/api/inventory")).json()

    matrix = data["aws_permission_matrix"]
    returned = {(r["service"], r["boto3_service"], r["operation"]) for r in matrix}
    expected = {(label, svc, op) for label, svc, op, _ in PERMISSION_PROBES}
    assert returned == expected


@pytest.mark.asyncio
async def test_inventory_provider_tiers_honest():
    """Capability tiers match the code: AWS has structured tools, Azure/GCP have none."""
    from httpx import ASGITransport, AsyncClient

    from api.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        data = (await client.get("/api/inventory")).json()

    providers = {p["name"]: p for p in data["providers"]}
    assert providers["aws"]["structured_tools"] > 0
    assert providers["azure"]["structured_tools"] == 0
    assert providers["gcp"]["structured_tools"] == 0
    # Azure is CLI-first; GCP is a pure stub with no CLI path.
    assert providers["azure"]["cli_access"] is True
    assert providers["azure"]["event_driven_and_polling"] is False
    assert providers["gcp"]["cli_access"] is False
