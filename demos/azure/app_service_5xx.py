#!/usr/bin/env python3
"""Azure demo — Web App returns 5xx due to a port misconfiguration.

Incident: a Linux container web app runs nginx (listens on port 80), but WEBSITES_PORT is set
to 8080, so App Service's health probe hits the wrong port — the container never goes healthy
and requests fail.

Prompt to give the agent (use the app name printed by `setup`):
    "My web app <name> isn't responding / returns errors — investigate."

What the agent should find (skill: azure-app-service-errors):
    - az webapp show           -> app state / availability
    - az webapp log tail       -> container not responding on the configured port (8080)
    - az monitor metrics list  -> Http5xx
    - az webapp config appsettings list -> WEBSITES_PORT=8080 (mismatch; nginx serves on 80)
    - Root cause: WEBSITES_PORT mismatch.

Usage:
    python demos/azure/app_service_5xx.py setup
    python demos/azure/app_service_5xx.py teardown
"""

from __future__ import annotations

import argparse
import os
import secrets
import shutil
import subprocess
import sys

RG = os.environ.get("ODO_DEMO_RG", "opendevops-demo-app-rg")
LOCATION = os.environ.get("ODO_DEMO_LOCATION", "westus2")
PLAN = "opendevops-demo-plan"
# App Service names are globally unique; teardown deletes the whole RG so the suffix needn't persist.
APP = os.environ.get("ODO_DEMO_APP", f"opendevops-demo-app-{secrets.token_hex(3)}")

_AZ = shutil.which("az") or "az"


def az(*args: str) -> None:
    print(f"$ az {' '.join(args)}")
    if subprocess.run([_AZ, *args], text=True).returncode != 0:
        sys.exit("\naz failed. See the error above.")


def setup() -> None:
    az("group", "create", "-n", RG, "-l", LOCATION, "--only-show-errors")
    az(
        "appservice", "plan", "create", "-g", RG, "-n", PLAN,
        "--is-linux", "--sku", "B1", "--location", LOCATION, "--only-show-errors",
    )
    az(
        "webapp", "create", "-g", RG, "-p", PLAN, "-n", APP,
        "--deployment-container-image-name", "nginx:latest", "--only-show-errors",
    )
    # The "incident": probe the wrong port. nginx serves on 80; tell App Service it's 8080.
    az(
        "webapp", "config", "appsettings", "set", "-g", RG, "-n", APP,
        "--settings", "WEBSITES_PORT=8080", "--only-show-errors",
    )
    print("\n✅ Setup complete — web app is misconfigured (WEBSITES_PORT=8080, nginx on 80).")
    print(f'\n   App name: {APP}')
    print(f'   Prompt:  "My web app {APP} isn\'t responding / returns errors — investigate."')
    print("   Expect:  container fails health checks on 8080 -> 5xx; root cause = port mismatch.")
    print("   (Give it ~1–2 min after setup for the container to cycle and metrics to populate.)")


def teardown() -> None:
    az("group", "delete", "-n", RG, "--yes", "--no-wait", "--only-show-errors")
    print(f"\n🧹 Teardown started — resource group {RG} is being deleted.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["setup", "teardown"])
    {"setup": setup, "teardown": teardown}[p.parse_args().action]()
