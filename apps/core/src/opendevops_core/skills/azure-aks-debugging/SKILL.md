---
name: azure-aks-debugging
description: Debug Azure Kubernetes Service (AKS) incidents — pods crashing, not ready, image/pull errors, node pressure — via az + kubectl
---

## AKS Debugging Investigation

All commands run through `run_bash_command`. Azure CLI (`az`) and `kubectl` are read-only here.

### Step 1 — Find the cluster and get credentials

- `az aks list -o json` — list clusters; note `name`, `resourceGroup`, `powerState`, `provisioningState`.
- `az aks show -g <rg> -n <cluster> -o json` — check `powerState.code` (Running?), `provisioningState`
  (Succeeded vs Failed), Kubernetes version, and `agentPoolProfiles` (node count, `provisioningState`).
- `az aks get-credentials -g <rg> -n <cluster>` — fetch the kubeconfig so `kubectl` works.
  (This writes to the org's isolated kubeconfig automatically.)

### Step 2 — Cluster-wide triage with kubectl

- `kubectl get nodes` — any `NotReady`? Node problems cascade into pod failures.
- `kubectl get pods -A` — scan for `CrashLoopBackOff`, `ImagePullBackOff`, `Pending`, `Error`,
  `OOMKilled`, high `RESTARTS`.
- `kubectl get events -A --sort-by=.lastTimestamp` — recent cluster events (scheduling failures,
  evictions, failed mounts, image pull errors).

### Step 3 — Drill into the failing workload

For a specific failing pod/namespace:
- `kubectl describe pod <pod> -n <ns>` — read `State`/`Last State` (look for `OOMKilled`, exit codes),
  `Events` (FailedScheduling, Back-off, Failed to pull image, readiness/liveness probe failures),
  and resource `Requests`/`Limits`.
- `kubectl logs <pod> -n <ns> --previous` — logs from the crashed container (use `--previous` for the
  prior crash); without `--previous` for the current one.
- `kubectl describe node <node>` — if scheduling/pressure suspected: `Conditions`
  (MemoryPressure, DiskPressure, PIDPressure), `Allocatable` vs allocated.

### Common Root Causes

| Symptom | Likely cause | Evidence |
|---|---|---|
| `CrashLoopBackOff` | App crashes on start / bad config / missing secret | `kubectl logs --previous`, describe Events |
| `OOMKilled` | Memory limit too low or leak | pod `Last State: OOMKilled`, node MemoryPressure |
| `ImagePullBackOff` | Bad image tag or registry auth (ACR) | describe Events "Failed to pull"; check ACR attach |
| `Pending` (unschedulable) | Insufficient CPU/mem, no matching node, taints | Events `FailedScheduling`; node Allocatable |
| Node `NotReady` | Kubelet/network issue, node pressure | `kubectl describe node`, `az aks show` agentPool state |
| Recent regression | New deploy/scale/upgrade | `az monitor activity-log list` (see azure-monitor-kql) + `kubectl rollout history` |

### Step 4 — Correlate with recent changes

- `az monitor activity-log list --resource-group <rg> --offset 3h -o json` — recent control-plane
  changes (scale, upgrade, config) on the cluster/node pools.
- `kubectl rollout history deployment/<name> -n <ns>` — recent workload rollouts.

### Notes
- ACR image pull failures: confirm the cluster's managed identity has `AcrPull` on the registry.
- If `az aks get-credentials` fails with auth errors, the connected service principal may lack the
  `Azure Kubernetes Service Cluster User Role` — surface that as the finding.
