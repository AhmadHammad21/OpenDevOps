#!/usr/bin/env python3
"""Azure demo — AKS pod stuck in CrashLoopBackOff.

Incident: a workload on an AKS cluster keeps crashing on startup (container exits 1), so it
churns in CrashLoopBackOff.

Prompt to give the agent:
    "Pods in my AKS cluster are failing — find the root cause."

What the agent should find (skill: azure-aks-debugging):
    - az aks list / az aks show          -> the cluster
    - az aks get-credentials             -> kubeconfig (agent does this in its own isolated dir)
    - kubectl get pods                   -> CrashLoopBackOff, climbing RESTARTS
    - kubectl describe pod / logs --previous -> container exits 1
    - Root cause: the container command fails on startup.

Requires `kubectl` locally for SETUP (run `az aks install-cli` if missing). Cluster creation
takes ~5 min. The agent's connected service principal needs the "Azure Kubernetes Service
Cluster User Role" on the cluster (Reader alone can't fetch kube credentials).

Usage:
    python demos/azure/aks_crashloop.py setup
    python demos/azure/aks_crashloop.py teardown

Node-size override (free-trial capacity — see README):
    ODO_DEMO_LOCATION, ODO_DEMO_AKS_NODE_SIZE
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

RG = os.environ.get("ODO_DEMO_RG", "opendevops-demo-aks-rg")
LOCATION = os.environ.get("ODO_DEMO_LOCATION", "westus2")
CLUSTER = "opendevops-demo-aks"
NODE_SIZE = os.environ.get("ODO_DEMO_AKS_NODE_SIZE", "Standard_B2ps_v2")  # ARM burstable

_AZ = shutil.which("az") or "az"
_KUBECTL = shutil.which("kubectl")


def az(*args: str) -> None:
    print(f"$ az {' '.join(args)}")
    if subprocess.run([_AZ, *args], text=True).returncode != 0:
        sys.exit("\naz failed. See the error above.")


def kubectl(*args: str) -> None:
    print(f"$ kubectl {' '.join(args)}")
    if subprocess.run([_KUBECTL, *args], text=True).returncode != 0:
        sys.exit("\nkubectl failed. See the error above.")


def setup() -> None:
    if not _KUBECTL:
        sys.exit("kubectl not found — install it first (e.g. `az aks install-cli`), then re-run.")
    az("group", "create", "-n", RG, "-l", LOCATION, "--only-show-errors")
    print("\n(Creating the AKS cluster — this takes a few minutes…)")
    az(
        "aks", "create", "-g", RG, "-n", CLUSTER,
        "--node-count", "1", "--node-vm-size", NODE_SIZE,
        "--generate-ssh-keys", "--only-show-errors",
    )
    az("aks", "get-credentials", "-g", RG, "-n", CLUSTER, "--overwrite-existing", "--only-show-errors")
    # The "incident": a workload that crashes on startup.
    kubectl(
        "run", "crashloop", "--image=busybox", "--restart=Always",
        "--", "/bin/sh", "-c", "echo booting; sleep 3; exit 1",
    )
    print("\nSetup complete - pod 'crashloop' will enter CrashLoopBackOff within ~30s.")
    print('\n   Prompt:  "Pods in my AKS cluster are failing — find the root cause."')
    print("   Expect:  az aks get-credentials -> kubectl get/describe/logs -> container exits 1.")
    print("   Note:    the agent's SP needs the 'Azure Kubernetes Service Cluster User Role'.")


def teardown() -> None:
    az("group", "delete", "-n", RG, "--yes", "--no-wait", "--only-show-errors")
    print(f"\nTeardown started - resource group {RG} is being deleted.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["setup", "teardown"])
    {"setup": setup, "teardown": teardown}[p.parse_args().action]()
