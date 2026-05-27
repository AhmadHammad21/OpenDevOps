---
name: azure-app-service-errors
description: Investigate Azure App Service / Functions errors — 5xx spikes, restarts, slow responses, failed deploys — via az + Azure Monitor
---

## Azure App Service / Functions Investigation

All commands run through `run_bash_command` with the Azure CLI (`az`).

### Step 1 — Identify the app and its state

- `az webapp list -o json` (or `az functionapp list -o json`) — find the app; note `resourceGroup`,
  `state` (Running/Stopped), `defaultHostName`.
- `az webapp show -g <rg> -n <app> -o json` — check `state`, `availabilityState`, `httpsOnly`,
  runtime stack, and `siteConfig` (alwaysOn, healthCheckPath).

### Step 2 — Pull the error signal from Azure Monitor

- `az monitor metrics list --resource <app-resource-id> --metric "Http5xx" "Http2xx" "Requests" "ResponseTime" --interval PT1M -o json`
  — correlate the 5xx spike with request volume and response time.
- High `Http5xx` with normal `Requests` → app-side failure. High `Http5xx` *with* a `Requests` spike →
  capacity/throttling. Rising `ResponseTime` before 5xx → downstream/dependency slowness.

### Step 3 — Read the application logs

- `az webapp log tail -g <rg> -n <app>` — live stream (good for an active incident).
- For deeper history, query Log Analytics if the app sends logs there (see `azure-monitor-kql`):
  `AppServiceHTTPLogs` and `AppServiceConsoleLogs` tables.

### Step 4 — Check for recent changes / restarts

- `az monitor activity-log list -g <rg> --offset 3h -o json` — recent deploys, config changes,
  restarts, scale operations on the app.
- Look for `Microsoft.Web/sites/restart`, slot swaps, app-setting changes, or a new deployment just
  before the incident window.

### Step 5 — Dependencies and config

- `az webapp config appsettings list -g <rg> -n <app> -o json` — missing/changed connection strings or
  settings (note: values may be masked; flag suspicious recent changes).
- If the app calls a DB / Key Vault / storage: check those resources' health and that the app's managed
  identity still has access (`az role assignment list --assignee <app-identity>`).

### Common Root Causes

| Symptom | Likely cause | Evidence |
|---|---|---|
| 5xx after a deploy | Bad release / config | activity-log deploy event; console logs stack trace |
| 5xx with request spike | Plan undersized / throttling | Requests spike + high CPU/memory metrics |
| Slow then 5xx | Downstream (DB/API) slow | rising ResponseTime; dependency errors in logs |
| App `Stopped` | Manual stop / crash / billing | `state: Stopped`; activity-log stop event |
| Cold starts (Functions) | Consumption plan scale-to-zero | high first-request latency; consider Premium plan |
| Missing setting/secret | Removed/rotated app setting or Key Vault ref | appsettings diff; "secret not found" in logs |
