"""Tool / permission inventory endpoint — a read-only trust artifact.

Exposes exactly what the agent can do (registered tools + their parameters, the bash
command allowlist, the AWS read-permission matrix, and per-provider capability tiers),
introspected live from the code so it never drifts. Read-only; no AWS calls.
"""

from __future__ import annotations

from fastapi import APIRouter
from opendevops_core.agent.inventory import build_inventory

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.get("")
async def get_inventory() -> dict:
    """Return the introspected tool/permission inventory."""
    return build_inventory()
