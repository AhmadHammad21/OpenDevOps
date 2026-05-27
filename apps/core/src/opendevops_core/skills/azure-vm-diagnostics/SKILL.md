---
name: azure-vm-diagnostics
description: Diagnose Azure VM and Virtual Machine Scale Set issues — unavailability, high CPU/memory, boot/health failures — via az + Azure Monitor
---

## Azure VM / Scale Set Diagnostics

All commands run through `run_bash_command` with `az`.

### Step 1 — Locate the VM and its power/provisioning state

- `az vm list -d -o json` — list VMs with `powerState` (`-d` includes runtime view); note
  `resourceGroup`, `powerState` (VM running?), `provisioningState`.
- `az vm get-instance-view -g <rg> -n <vm> -o json` — detailed `statuses`: power state, OS state,
  and any provisioning/extension errors.
- Scale sets: `az vmss list -o json`, then `az vmss list-instances -g <rg> -n <vmss> -o json` and
  `az vmss get-instance-view -g <rg> -n <vmss> --instance-id <id> -o json`.

### Step 2 — Resource health metrics

- `az monitor metrics list --resource <vm-id> --metric "Percentage CPU" "Available Memory Bytes" "Network In Total" "Network Out Total" "OS Disk IOPS Consumed Percentage" --interval PT1M --offset 1h -o json`
- High `Percentage CPU` sustained near 100%, low `Available Memory Bytes`, or disk IOPS at 100% →
  resource exhaustion. Correlate the onset time with recent changes (Step 4).

### Step 3 — Boot / health diagnostics

- `az vm boot-diagnostics get-boot-log -g <rg> -n <vm>` — serial/boot log (kernel panics, fsck, cloud-init
  failures) when a VM won't come up.
- Check extensions: in `get-instance-view`, look for failed extensions (custom script, monitoring agent).

### Step 4 — Recent changes

- `az monitor activity-log list -g <rg> --offset 3h -o json` — resize, restart, deallocate,
  redeploy, NSG/disk changes, or autoscale actions on the VM/scale set just before the incident.

### Common Root Causes

| Symptom | Likely cause | Evidence |
|---|---|---|
| VM unreachable, `powerState` not running | Deallocated/stopped (manual or autoscale), host issue | instance-view statuses; activity-log stop/deallocate |
| Sustained 100% CPU | Undersized SKU or runaway process | `Percentage CPU` metric; scale up / investigate workload |
| Low available memory / swapping | Memory pressure | `Available Memory Bytes`; resize or fix leak |
| Disk at 100% IOPS | Disk SKU too slow for load | `OS Disk IOPS Consumed Percentage`; upgrade to Premium SSD |
| Won't boot | Bad image/cloud-init, corrupt disk | boot-diagnostics serial log |
| Scale set instances unhealthy | Failing health probe / bad model update | vmss instance-view; recent model/upgrade in activity log |
| Network unreachable | NSG/route change | activity-log NSG change; check effective rules |
