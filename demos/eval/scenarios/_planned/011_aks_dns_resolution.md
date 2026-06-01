# Planned scenario — AKS DNS resolution failure

**Status:** designed, not yet executable. Tracked in GitHub issue (see footer).
The underscore prefix on this directory keeps the runner from picking it up.

## The incident

Real-world case described by a practicing Azure SRE: an AKS cluster can't
pull images from ACR (Azure Container Registry), but **no clear error
surfaces** — pulls just hang and time out. The triage path goes:

1. Check IAM / permissions (cluster identity has `AcrPull` role) — fine.
2. Check pod / pull-secret config — fine.
3. Deploy a diagnostic pod, `kubectl exec` into it, try to resolve the ACR
   hostname from inside the cluster — `nxdomain` / no answer.
4. Realize the cluster runs on a private VNet, ACR is in a private endpoint
   with a **private DNS zone**, and the VNet isn't linked to the zone.
   The pod has no DNS route to the ACR's private IP.

Root cause: **missing private-DNS-zone-to-VNet link** (or a misconfigured
`vnet link` / `coreDNS` override). Symptom: pods can't resolve the ACR's
private FQDN; only visible by `nslookup` from inside a pod.

## Why this is a good eval scenario

- Multi-layer diagnosis (RBAC → pod config → DNS → networking).
- Forces the agent to use `kubectl exec` to run a diagnostic pod — the same
  pattern human SREs use.
- Tests cross-resource reasoning (the failing resource is the pod; the
  broken resource is the DNS zone link).
- Realistic: this exact incident shows up regularly in enterprise Azure
  deployments and is hard to diagnose without the right mental model.

## Demo-script setup (TODO — needs implementation)

The setup script (`demos/azure/aks_dns_resolution.py`) needs to:

1. Create resource group + VNet with subnet for AKS.
2. Create an AKS cluster with kubenet/CNI and **private API server**.
3. Create an ACR with private endpoint connected to the VNet.
4. **Deliberately skip** the `az network private-dns link vnet create`
   that would link `privatelink.azurecr.io` to the cluster's VNet.
5. Deploy a small workload (`kubectl apply`) that references an image
   in the ACR. Pod stays in `ImagePullBackOff`.

Teardown: delete the resource group (async, releases all child resources).

**Cost / time**: AKS provisioning takes 10-15 min. Standard SKU runs ~$0.10/hr.
Roll setup-time budget into `timeout_seconds` and `propagation_seconds`.

## Proposed `scenario.json`

```json
{
  "name": "AKS pods can't pull from ACR — missing private DNS zone link",
  "cloud": "azure",
  "demo": "demos/azure/aks_dns_resolution.py",
  "prompt": "Pods in opendevops-demo-aks are stuck in ImagePullBackOff. Permissions look fine. What's wrong?",
  "timeout_seconds": 360,
  "propagation_seconds": 120,
  "ground_truth": {
    "root_cause_category": ["DEPENDENCY_ISSUE", "SYSTEM_CHANGE", "COMPONENT_FAILURE"],
    "services_affected": ["AKS", "ACR", "Private DNS"],
    "evidence_keywords": ["dns", "private", "resolution"],
    "expected_tools_any_of": [
      "run_bash_command",
      "use_skill"
    ]
  }
}
```

## When to build this

- After we have ≥10 working AWS scenarios (so the framework's mostly proven
  before we sink AKS provisioning time into it).
- Before any "enterprise Azure pitch" — this is the kind of debugging story
  that convinces SREs the agent is useful for real production work, not
  just textbook Lambda errors.
