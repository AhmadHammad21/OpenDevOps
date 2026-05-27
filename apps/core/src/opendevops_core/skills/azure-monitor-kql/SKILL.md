---
name: azure-monitor-kql
description: Query Azure Monitor metrics, the Activity Log, and Log Analytics (KQL) to find anomalies and recent changes across Azure resources
---

## Azure Monitor & Log Analytics (KQL)

The cross-cutting Azure observability toolkit. Use it from any Azure investigation. All via
`run_bash_command` with `az`.

### Recent changes — the Activity Log (always check early)

The Activity Log is Azure's audit trail (the CloudTrail equivalent). Most incidents follow a change.

- `az monitor activity-log list --offset 3h -o json` — subscription-wide recent operations.
- Scope it: `--resource-group <rg>` or `--resource-id <id>`.
- Look for write/action operations just before the incident: deploys, scale, restart, delete,
  config/role changes. Field `operationName`, `status`, `caller`, `eventTimestamp`.

### Metrics — Azure Monitor

- List available metrics for a resource: `az monitor metrics list-definitions --resource <id> -o table`.
- Pull a metric: `az monitor metrics list --resource <id> --metric "<Name>" --interval PT1M --offset 1h -o json`.
- Common metrics: VMs `Percentage CPU`, App Service `Http5xx`/`ResponseTime`, AKS
  `node_cpu_usage_percentage`/`kube_pod_status_ready`, SQL DB `cpu_percent`/`dtu_consumption_percent`,
  Storage `Availability`/`Transactions`.

### Logs — Log Analytics (KQL)

If resources send logs to a Log Analytics workspace:

- Find the workspace: `az monitor log-analytics workspace list -o json` (note `customerId` = workspace GUID).
- Run KQL: `az monitor log-analytics query -w <workspace-guid> --analytics-query "<KQL>" -o json`.

Useful KQL patterns (last hour):
```kusto
// App Service 5xx by operation
AppServiceHTTPLogs | where TimeGenerated > ago(1h) | where ScStatus >= 500
| summarize count() by CsUriStem, ScStatus | order by count_ desc

// AKS container logs containing errors
ContainerLogV2 | where TimeGenerated > ago(1h) | where LogMessage contains "error"
| summarize count() by PodName | order by count_ desc

// VM heartbeat gaps (node down)
Heartbeat | where TimeGenerated > ago(15m) | summarize LastSeen=max(TimeGenerated) by Computer
```

### Method

1. Activity Log first — did something change?
2. Metrics — quantify and time-box the anomaly (when did it start, how big?).
3. Logs (KQL) — find the concrete error and the affected component.
4. Correlate the metric spike / log errors with the change from step 1 to form the root cause.

### Notes
- KQL queries need the workspace GUID (`customerId`), not the resource name.
- If `az monitor log-analytics query` fails with auth, the service principal likely lacks
  `Log Analytics Reader` — surface that.
