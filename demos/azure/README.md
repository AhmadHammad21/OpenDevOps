# OpenDevOps Agent — Azure Demo Scenarios

Reproducible **Azure** incidents for demoing / recording the agent. Each script breaks
something in **your** Azure subscription in a controlled, reversible way, then you point
the agent at it and watch it investigate via the Azure CLI (`az`) + `kubectl`.

Everything is read-only on the agent side — these scripts just create the broken state.
Each case lives in its **own resource group** (`opendevops-demo-*-rg`) and every script has a
`teardown` action that deletes that group.

> ⚠️ **These create real Azure resources.** The VM and App Service cases are a few cents
> (deallocated/Basic tier); the **AKS** case runs a managed cluster — costs a little while up.
> **Always run `teardown`** when done. Use a sandbox subscription / your free-trial credit.

---

## Prerequisites

```bash
# 1. Log in (the SETUP scripts use YOUR interactive login; needs Contributor to create resources)
az login
az account set --subscription <your-subscription-id>

# 2. Run a scenario (plain python — only the `az` CLI is required, no extra deps)
python demos/azure/vm_deallocated.py setup
python demos/azure/vm_deallocated.py teardown
```

The identity running the **scripts** needs **Contributor** (to create resources). The service
principal the **agent** uses (connected in the product under **Settings → Cloud Accounts → Azure**)
only needs **Reader** on the subscription — plus the **"Azure Kubernetes Service Cluster User Role"**
for the AKS case (so `az aks get-credentials` → `kubectl` works). See
[connect-aws-account.md](../../../OpenDevOps-Product/docs/connect-aws-account.md) in the product repo
for the Azure connect flow.

---

## Scenario index

| Tier | Script | Incident | Skill / tools exercised |
|---|---|---|---|
| Easy ⭐ | `vm_deallocated.py` | VM stopped (deallocated) out from under you | `azure-vm-diagnostics` — `az vm get-instance-view` + `az monitor activity-log list` |
| Mid | `app_service_5xx.py` | Web app returns 5xx — `WEBSITES_PORT` mismatch (container on 80, probe on 8080) | `azure-app-service-errors` — `az webapp show/log`, `az monitor metrics` |
| Hard ⭐ | `aks_crashloop.py` | AKS pod in `CrashLoopBackOff` | `azure-aks-debugging` — `az aks get-credentials` → `kubectl get/describe/logs` |

⭐ = strongest demos. Each script's docstring has the exact prompt to give the agent and what it
should find.

---

## Suggested demo flow

1. `setup` the scenario — it prints the **prompt** and the **resource name** to use.
2. In the product, make sure the org's connected Azure account points at **this** subscription.
3. Open the chat and paste the prompt.
4. Watch the tool-call inspector chain `az` (and for AKS, `kubectl`) and land a root cause.
5. `teardown`.

### Capacity gotcha (VM case)
Azure free-trial / busy regions often reject small VM SKUs with
`SkuNotAvailable: ... Capacity Restrictions`. The VM script defaults to an ARM size/region that is
widely available, but you can override:

```bash
ODO_DEMO_LOCATION=westus2 ODO_DEMO_VM_SIZE=Standard_B2ps_v2 python demos/azure/vm_deallocated.py setup
```

Find a size that's available for *your* subscription in a region:
```bash
az vm list-skus --size Standard_B1s --all \
  --query "[?length(restrictions)==\`0\`].locationInfo[0].location" -o tsv | sort -u
# or, small sizes available in one region:
az vm list-skus -l westus2 --all \
  --query "[?length(restrictions)==\`0\` && starts_with(name,'Standard_B')].name" -o tsv | sort -u
```

### Activity Log lag
The Azure Activity Log (used by the VM case for "who changed what") can take **1–2 minutes** to show
a new event. Run `setup`, wait a moment, *then* investigate so the agent can correlate the change.

### AKS note
`aks_crashloop.py setup` needs **`kubectl`** locally (`az aks install-cli` if you don't have it) and
takes ~5 minutes to create the cluster. The agent's connected SP needs the **AKS Cluster User Role**.

---

## Cleanup

Each script's `teardown` deletes its resource group:
```bash
python demos/azure/vm_deallocated.py teardown
python demos/azure/app_service_5xx.py teardown
python demos/azure/aks_crashloop.py teardown
```

For recording GIFs / short demos, see the tips in the AWS [README](../aws/README.md#recording-gifs--short-demos).
