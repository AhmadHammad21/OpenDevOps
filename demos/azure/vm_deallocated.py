#!/usr/bin/env python3
"""Azure demo — VM stopped (deallocated) out from under you.

Incident: a VM is unreachable because it was deallocated (stopped), not because it crashed.

Prompt to give the agent:
    "My VM opendevops-demo-vm is unreachable — what happened?"

What the agent should find (skill: azure-vm-diagnostics):
    - az vm get-instance-view  -> powerState: "VM deallocated"
    - az monitor activity-log list -> the "Deallocate Virtual Machine" event (when + who)
    - Root cause: the VM was intentionally/accidentally stopped, not a failure.

Usage:
    python demos/azure/vm_deallocated.py setup
    python demos/azure/vm_deallocated.py teardown

Capacity overrides (see README — free-trial regions often reject small SKUs):
    ODO_DEMO_LOCATION, ODO_DEMO_VM_SIZE, ODO_DEMO_VM_IMAGE
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

RG = os.environ.get("ODO_DEMO_RG", "opendevops-demo-vm-rg")
LOCATION = os.environ.get("ODO_DEMO_LOCATION", "westus2")
VM = "opendevops-demo-vm"
SIZE = os.environ.get("ODO_DEMO_VM_SIZE", "Standard_B2ps_v2")  # ARM burstable, widely available
IMAGE = os.environ.get(
    "ODO_DEMO_VM_IMAGE", "Canonical:0001-com-ubuntu-server-jammy:22_04-lts-arm64:latest"
)

_AZ = shutil.which("az") or "az"


def az(*args: str, capture: bool = False) -> str:
    print(f"$ az {' '.join(args)}")
    r = subprocess.run([_AZ, *args], text=True, capture_output=capture)
    if r.returncode != 0:
        if capture and r.stderr:
            sys.stderr.write(r.stderr)
        sys.exit(f"\naz failed (exit {r.returncode}). See the error above.")
    return (r.stdout or "").strip()


def setup() -> None:
    az("group", "create", "-n", RG, "-l", LOCATION, "--only-show-errors")
    az(
        "vm", "create", "-g", RG, "-n", VM,
        "--image", IMAGE, "--size", SIZE, "--location", LOCATION,
        "--admin-username", "azureuser", "--generate-ssh-keys", "--only-show-errors",
    )
    # The "incident": stop/deallocate the VM.
    az("vm", "deallocate", "-g", RG, "-n", VM, "--only-show-errors")
    print("\n✅ Setup complete — VM is deallocated.")
    print(f'\n   Prompt:  "My VM {VM} is unreachable — what happened?"')
    print("   Expect:  powerState=deallocated + the Deallocate event in the Activity Log.")
    print("   (Activity Log can lag 1–2 min; wait a moment before investigating.)")


def teardown() -> None:
    az("group", "delete", "-n", RG, "--yes", "--no-wait", "--only-show-errors")
    print(f"\n🧹 Teardown started — resource group {RG} is being deleted.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["setup", "teardown"])
    {"setup": setup, "teardown": teardown}[p.parse_args().action]()
