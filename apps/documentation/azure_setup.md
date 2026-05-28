# Azure Setup Guide

This guide covers how to give OpenDevOps Agent **read-only** access to your Azure subscription —
either with a dedicated **service principal** (for servers / the hosted product) or your **personal
login** (for quick local testing).

The agent investigates Azure through the read-only Azure CLI (`az`) and `kubectl` (for AKS) — it
never creates, deletes, or modifies anything. So you only ever grant **read** roles.

> **AWS users:** the analogous guide is [iam_setup.md](./iam_setup.md). One key difference: AWS reads
> credentials from environment variables, but the **`az` CLI must actually be logged in** (`az login`)
> — setting `AZURE_*` env vars alone does **not** authenticate `az`.

---

## Credential options

| Method | When to use |
|---|---|
| **Service principal** (app registration) | Self-hosted server, Docker, Railway, CI — and the hosted product |
| **Personal login** (`az login`) | Local dev / quick testing with your own account |
| **Managed identity** | Agent running *on* Azure (VM, AKS, Container Apps) — no secrets |

---

## Option A — Service principal (recommended for servers / non-interactive)

A service principal is the Azure equivalent of an IAM user with an access key — a dedicated identity
with its own credentials and scoped, read-only roles.

### Step 1 — Create it

**CLI (one command):**
```bash
az login
SUB=$(az account show --query id -o tsv)
az ad sp create-for-rbac --name opendevops-agent --role Reader --scopes /subscriptions/$SUB
```
The output gives you everything you need:
```
{
  "appId":    "...",   # Client ID
  "password": "...",   # Client Secret  (shown ONCE — copy it now)
  "tenant":   "..."    # Tenant ID
}
```
Subscription ID is the one you passed in `--scopes`.

**Portal alternative:** Microsoft Entra ID → App registrations → New registration → copy the
**Application (client) ID** + **Directory (tenant) ID**; Certificates & secrets → New client secret →
copy the **Value**; then assign the **Reader** role (Step 2).

### Step 2 — Assign roles (read-only)

| Role | Scope | Needed for |
|---|---|---|
| **Reader** | Subscription (or resource group) | **Baseline** — read every resource: VMs, App Service, Activity Log, metrics, etc. Required. |
| **Azure Kubernetes Service Cluster User Role** | The AKS cluster (or subscription) | Only for **AKS debugging** — `az aks get-credentials` is an *action*, not a read, so `Reader` alone can't fetch the kubeconfig. |
| **Log Analytics Reader** | The Log Analytics workspace | Only if you run **KQL log queries** (`az monitor log-analytics query`). |

Assign extra roles via **Subscription / cluster → Access control (IAM) → Add role assignment**, or:
```bash
az role assignment create --assignee <CLIENT_ID> \
  --role "Azure Kubernetes Service Cluster User Role" \
  --scope <aks-cluster-resource-id>
```
> No **write** roles are ever needed — the agent's bash tool only allows read-only `az` verbs
> (`list`, `show`, `get-*`, `describe`, `tail`, `query`). Granting Contributor/Owner is unnecessary
> and discouraged.

### Step 3 — Give the credentials to the agent

**Self-hosted (OSS):** the agent's `az` calls use the host's logged-in CLI session, so **log the
service principal in once on the host**:
```bash
az login --service-principal -u <CLIENT_ID> -p <CLIENT_SECRET> --tenant <TENANT_ID>
az account set --subscription <SUBSCRIPTION_ID>
```
(Setting `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` env vars is **not** enough for the CLI — you must
`az login`.) On a server/container, run this at startup.

**Hosted product:** don't log in on a shared host. Instead paste the tenant / client / secret /
subscription into **Settings → Cloud Accounts → Azure** — the product stores the secret encrypted and
performs an isolated, per-organization `az login` per request. See the product's
`docs/connect-aws-account.md` for the full flow.

---

## Option B — Personal user access (quick local testing)

The fastest way to try the agent against your own subscription:
```bash
az login                      # opens a browser; sign in with your account
az account set --subscription <SUBSCRIPTION_ID>   # if you have more than one
```
The agent's `az` commands then run as **you**, with your own RBAC. Great for local experimentation;
**not** for shared servers (the agent would act with your full personal permissions). For anything
shared, use a scoped service principal (Option A).

---

## Option C — Managed identity (agent running on Azure)

If you run the agent on an Azure VM, AKS, or Container App, enable a **system-assigned managed
identity**, grant it **Reader**, and log in with no secrets:
```bash
az login --identity
```

---

## Verify

```bash
az account show -o table            # confirms which subscription/identity is active
az group list -o table              # confirms read access works
# AKS only:
az aks get-credentials -g <rg> -n <cluster> && kubectl get nodes
```
Then ask the agent an Azure question (e.g. *"list my resource groups"*) and watch it run `az` via the
bash tool.

---

## Self-host vs hosted product

- **Self-host (this guide):** one `az` session on the host (service principal or personal login),
  one subscription. The agent inherits it.
- **Hosted product:** each organization connects its **own** service principal in the UI; credentials
  are encrypted and isolated per org, and the agent assumes the caller-org's identity per request.
