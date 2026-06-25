# Database Schema

PostgreSQL 13+. Run migrations in order from `migrations/` to set up the schema.

LangGraph's own tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`) are
created automatically by `AsyncPostgresSaver.setup()` on startup — they live in the same
database but are not listed here.

---

## Running migrations

```bash
psql $DATABASE_URL -f migrations/001_initial.sql
psql $DATABASE_URL -f migrations/002_soft_delete.sql
psql $DATABASE_URL -f migrations/003_usage_events_metadata.sql
psql $DATABASE_URL -f migrations/004_users_rbac.sql
psql $DATABASE_URL -f migrations/005_alerts.sql
psql $DATABASE_URL -f migrations/006_app_config.sql
# Continue through the remaining numbered migrations, including:
psql $DATABASE_URL -f migrations/012_incident_claims.sql
```

All migrations are idempotent (`IF NOT EXISTS`, `IF column does not already exist`).

---

## Tables

### `users`
User accounts with password-based auth and RBAC roles.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `org_id` | UUID FK → organizations | Nullable — unused in OSS single-tenant |
| `email` | TEXT UNIQUE | |
| `name` | TEXT | |
| `password_hash` | TEXT | bcrypt hash. NULL for pre-RBAC rows |
| `role` | TEXT | `admin` or `user`. Default `user` |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

**Constraint:** `role IN ('admin', 'user')`

**First registered user** (first row with a `password_hash`) automatically gets `role = 'admin'`.

---

### `sessions`
One session = one LangGraph `thread_id`. The `id` column **is** the `thread_id` passed to LangGraph.

`user_id` and `org_id` are nullable so the app works with auth disabled.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Same value as LangGraph `thread_id` |
| `user_id` | UUID FK → users | Nullable |
| `org_id` | UUID FK → organizations | Nullable |
| `aws_profile_id` | UUID FK → aws_profiles | Nullable |
| `title` | TEXT | Auto-set from first 80 chars of first user message |
| `model` | TEXT | LiteLLM model ID used |
| `aws_region` | TEXT | AWS region at time of session |
| `is_deleted` | BOOLEAN | Soft delete — `false` by default |
| `deleted_at` | TIMESTAMPTZ | Set when soft-deleted |
| `created_at` | TIMESTAMPTZ | |
| `last_active_at` | TIMESTAMPTZ | Updated on every agent turn |

**Indexes:** `user_id`, `org_id`, `last_active_at DESC`, `is_deleted` (partial, where false)

---

### `messages`
Every user and assistant message in a session, in order.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK → sessions | Cascade delete |
| `role` | TEXT | `user` or `assistant` |
| `content` | TEXT | Full message text |
| `metadata` | JSONB | LangChain `run_id`, `tags`, `RunnableConfig` extras |
| `created_at` | TIMESTAMPTZ | |

**Indexes:** `(session_id, created_at)`

---

### `tool_calls`
Every AWS tool invocation per agent turn.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK → sessions | |
| `message_id` | UUID FK → messages | Links to the assistant message. Nullable. |
| `tool_name` | TEXT | e.g. `get_alarms`, `query_logs_insights` |
| `args` | JSONB | Input arguments |
| `result` | JSONB | Tool output |
| `error` | TEXT | Non-null when tool returned `{"error": ...}` |
| `duration_ms` | INTEGER | |
| `created_at` | TIMESTAMPTZ | |

**Indexes:** `session_id`, `message_id`, `tool_name`

---

### `usage_events`
One row per completed agent turn: token counts, cost, latency.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK → sessions | |
| `message_id` | UUID FK → messages | |
| `model` | TEXT | LiteLLM model ID |
| `input_tokens` | INTEGER | |
| `output_tokens` | INTEGER | |
| `cost_usd` | NUMERIC(14,8) | Computed from LiteLLM pricing map |
| `latency_ms` | INTEGER | Wall-clock time for the full turn |
| `tool_call_count` | INTEGER | Number of tool calls in this turn |
| `metadata` | JSONB | Per-event context (e.g. `summarization: true`, `chars_removed`) |
| `created_at` | TIMESTAMPTZ | |

**Indexes:** `session_id`, `created_at DESC`

---

### `organizations` *(future — Phase 3)*
Top-level tenant for multi-org / SaaS support. Table exists in the schema but is not used by the application in the current OSS release.

### `aws_profiles` *(future — Phase 3)*
Per-org named AWS connection configs for multi-account support. Table exists but not yet wired up.

### `findings` *(future — Phase 2)*
Structured root-cause analysis rows extracted from agent final answers. Table exists but not yet populated. Migration `015` adds a `hypotheses JSONB` column (default `[]`) for the ranked-hypotheses conclusion schema; the replayable evidence pack currently reads the conclusion straight from `tool_calls` (the `submit_investigation` row) rather than from this table.

### `api_keys` *(future — Phase 3)*
Hashed API keys for programmatic access. Table exists but not yet implemented.

### `alerts`
Persisted event-driven and proactive polling investigation results shown on `/monitoring`.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `service` | TEXT | Affected service/resource label |
| `error` | TEXT | Root cause summary |
| `resolution` | TEXT | Mitigation steps joined as text |
| `confidence` | TEXT | `HIGH`, `MEDIUM`, or `LOW` |
| `sns_sent` | BOOLEAN | Whether SNS publish succeeded |
| `dedup_key` | TEXT | Canonical incident key used by the poller/event consumer |
| `status` | TEXT | `completed` or `failed` |
| `session_id` | UUID FK → sessions | Investigation session that produced the alert |
| `trigger_source` | TEXT | `poller` or `event_consumer` |
| `created_at` | TIMESTAMPTZ | |

### `incident_claims`
Durable pre-investigation claims used to prevent duplicate autonomous agent runs.

| Column | Type | Notes |
|---|---|---|
| `incident_key` | TEXT PK | Canonical key such as `cloudwatch_alarm:us-east-1:high-error-rate` |
| `trigger_source` | TEXT | `poller` or `event_consumer` |
| `status` | TEXT | `claimed`, `completed`, or `failed` |
| `session_id` | UUID FK → sessions | Set when an investigation completes |
| `claimed_at` | TIMESTAMPTZ | Last time the incident was claimed |
| `completed_at` | TIMESTAMPTZ | Set after a completed or failed investigation |

### `app_config`
Application-level key/value configuration shared by all server instances. The init wizard stores its setup and event-infrastructure state under key `init`.

| Column | Type | Notes |
|---|---|---|
| `key` | TEXT PK | e.g. `init` |
| `value` | JSONB | Setup state, AWS region, SQS URL, rule ARNs |
| `updated_at` | TIMESTAMPTZ | |

---

## Entity Relationship

```
users
sessions ──── messages ──── tool_calls
         └─────────────── usage_events
```

---

## Key Design Decisions

- `sessions.id` is the LangGraph `thread_id` — no join needed to link conversation history to app data.
- `messages.metadata JSONB` stores arbitrary LangChain runtime context without schema changes.
- `tool_calls.error` is a separate TEXT column (not just checking `result.error`) so failed calls are queryable with `WHERE error IS NOT NULL`.
- `usage_events.cost_usd` is computed by the app from the LiteLLM pricing map — not trusted from the API.
- `usage_events.metadata` tracks per-turn context like whether the turn triggered conversation summarization.
- `user_id` / `org_id` on sessions are nullable intentionally: the app works without auth (`JWT_SECRET` unset).
- `password_hash` on users is nullable: pre-RBAC rows and future OAuth users won't have one.
