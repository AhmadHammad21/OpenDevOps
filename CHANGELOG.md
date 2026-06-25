# Changelog

Notable changes to OpenDevOps Agent (open-source core + backend).

## [Unreleased] — 2026-05

### Added — Multi-cloud (Azure)
- **Azure support, CLI-first.** The agent investigates Azure through the read-only Azure CLI
  (`az`) and `kubectl` (for AKS) plus runbook skills — no separate SDK tools:
  - `az` added to the bash-tool allowlist (read-only verbs only: `list`/`show`/`get-*`/`describe`/
    `tail`/`query`; create/delete/`invoke`/`run-command` blocked).
  - 4 Azure skills: `azure-aks-debugging`, `azure-app-service-errors`, `azure-monitor-kql`,
    `azure-vm-diagnostics` (drop-in `SKILL.md`).
  - `providers/azure/credentials.py` — service-principal auth into an isolated, cached
    `AZURE_CONFIG_DIR`; `verify_service_principal` via `azure-identity`.
  - System prompt is now cloud-neutral and `CLOUD_PROVIDER`-aware.
- **Use multiple clouds at once.** A provider→account map lets a host/org have AWS + Azure active
  together; the bash tool resolves credentials per command (`aws`→AWS, `az`/`kubectl`→Azure).
- **Azure setup guide** (`apps/documentation/azure_setup.md`) — service principal + personal
  `az login`, read-only roles (Reader, AKS Cluster User Role, Log Analytics Reader); cross-linked
  from `iam_setup.md`.
- **Azure demo scenarios** (`demos/azure/`): VM deallocated, App Service 5xx, AKS CrashLoopBackOff —
  reproducible `setup`/`teardown` scripts + README.

### Added — credential seam
- Provider-agnostic **`cloud_accounts`** table (migration `014`) and a ContextVar-based credential
  resolver. AWS resolves via assume-role / access-key; falls back to env/profile when unset (OSS).
- **Org-scoping seam** for downstream multi-tenant: optional `org_id` on `get_dashboard_stats`,
  `get_history_stats`, `search_sessions`, `list_users`, `get_alerts`, `get_alert`
  (`None` = unscoped — OSS behavior unchanged).
- `CREDENTIALS_ENCRYPTION_KEY` (Fernet) for encrypting stored account secrets.

### Added — Replayable evidence pack & ranked hypotheses
- **Evidence pack endpoint** — read-only `GET /api/sessions/{id}/evidence` returns the
  investigation's ranked hypotheses, each with cited evidence linked to the supporting tool
  call, the exact query/command that ran, and a deterministic AWS-console deeplink. Reads the
  conclusion from the persisted `submit_investigation` tool call (the `findings` table stays
  an unwritten placeholder). Pure builder + console-deeplink encoder live in
  `opendevops_core/agent/evidence.py`; `db.get_evidence()` added to the `DatabaseBackend` ABC
  (default + all three backends). Frontend `EvidencePanel` renders grouped hypotheses + replay
  cards with copy-to-clipboard and JSON export. See `apps/documentation/evidence_pack.md`.
- **Ranked hypotheses conclusion schema** — `submit_investigation` now emits
  `hypotheses: list[dict]` (`{hypothesis, evidence, confidence}`) alongside the legacy
  `root_cause_summary` + flat `evidence[]` (preserved for backward compatibility). Migration
  `015` adds `findings.hypotheses JSONB` (postgres only). The builder falls back to one
  synthetic hypothesis when `hypotheses` is absent so pre-existing investigations still render.

### Changed
- **README** reframed as multi-cloud (AWS + Azure) with links to both setup guides.
- **`demos/`** reorganized into `demos/aws/` + `demos/azure/` with a top-level index.
- **Backend Docker image** builds from the repo root (fixes the monorepo `opendevops-core` path
  dependency) and bakes in AWS CLI, **Azure CLI, kubectl, kubelogin**.
- **docker-compose**: three backends to choose from — `docker-compose.yml` (postgres),
  `docker-compose.sqlite.yml`, `docker-compose.memory.yml`; mounts `~/.aws` + `~/.azure`.

### Security
- **Cross-provider fail-closed:** a scoped org never falls back to the platform's credentials —
  `aws`/AWS tools are denied when no AWS account is connected, and `az` when no Azure account is
  (and vice-versa). No connected accounts at all → ambient host creds (self-host).
- Tool cache keyed on the active credential identity (no cross-account result bleed).
- Bash `aws`/`az` calls run with the org's assumed-role / service-principal credentials injected
  per command (never the platform's ambient creds for a scoped org).
