# Database Schema

PostgreSQL 13+. Run `migrations/001_initial.sql` to create all tables.

LangGraph's own tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`) are
created automatically by `AsyncPostgresSaver.setup()` on startup — they live in the same
database but are not listed here.

---

## Tables

### `organizations`
Top-level tenant. A single-user install can have one default org.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `name` | TEXT | Display name |
| `slug` | TEXT UNIQUE | URL-safe identifier |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

---

### `users`
User accounts, scoped to an org.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | UUID FK → organizations | Cascade delete |
| `email` | TEXT UNIQUE | |
| `name` | TEXT | |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

---

### `aws_profiles`
Named AWS connection configs per org. Enables multi-account support (Phase 3).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | UUID FK → organizations | |
| `name` | TEXT | Unique per org |
| `aws_region` | TEXT | Default `us-east-1` |
| `aws_profile` | TEXT | Named profile in `~/.aws/credentials` |
| `description` | TEXT | |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

---

### `sessions`
One session = one LangGraph `thread_id`. The `id` column **is** the `thread_id` passed to LangGraph.

`user_id` and `org_id` are nullable so the app works before auth is wired up.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Same value as LangGraph `thread_id` |
| `user_id` | UUID FK → users | Nullable |
| `org_id` | UUID FK → organizations | Nullable |
| `aws_profile_id` | UUID FK → aws_profiles | Nullable |
| `title` | TEXT | Auto-set from first 80 chars of first user message |
| `model` | TEXT | OpenRouter model ID used |
| `aws_region` | TEXT | AWS region at time of session |
| `created_at` | TIMESTAMPTZ | |
| `last_active_at` | TIMESTAMPTZ | Updated on every agent turn |

**Indexes:** `user_id`, `org_id`, `last_active_at DESC`

---

### `messages`
Every user and assistant message in a session, in order.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK → sessions | Cascade delete |
| `role` | TEXT | `user` or `assistant` |
| `content` | TEXT | Full message text |
| `metadata` | JSONB | LangChain `run_id`, `tags`, `RunnableConfig` extras, any runtime context |
| `created_at` | TIMESTAMPTZ | |

**Indexes:** `(session_id, created_at)`

---

### `tool_calls`
Every AWS tool invocation per agent turn. Multiple rows per assistant message.

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
| `message_id` | UUID FK → messages | Links to the assistant message |
| `model` | TEXT | OpenRouter model ID |
| `input_tokens` | INTEGER | |
| `output_tokens` | INTEGER | |
| `cost_usd` | NUMERIC(14,8) | Computed from pricing map |
| `latency_ms` | INTEGER | Wall-clock time for the full turn |
| `tool_call_count` | INTEGER | Number of tool calls in this turn |
| `created_at` | TIMESTAMPTZ | |

**Indexes:** `session_id`, `created_at DESC`

---

### `findings`
Structured root-cause analysis extracted from the agent's final answer (Phase 2).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK → sessions | |
| `message_id` | UUID FK → messages | |
| `root_cause_category` | TEXT | `SYSTEM_CHANGE`, `INPUT_ANOMALY`, `RESOURCE_LIMIT`, `COMPONENT_FAILURE`, `DEPENDENCY_ISSUE`, `UNKNOWN` |
| `root_cause_summary` | TEXT | |
| `confidence` | TEXT | `HIGH`, `MEDIUM`, `LOW` |
| `services_affected` | TEXT[] | |
| `mitigation_steps` | TEXT[] | |
| `evidence` | TEXT[] | |
| `raw_json` | JSONB | Full structured JSON block from agent |
| `created_at` | TIMESTAMPTZ | |

**Indexes:** `session_id`, `root_cause_category`

---

### `api_keys` *(Phase 3)*
Hashed API keys for programmatic/CLI access.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | UUID FK → organizations | |
| `user_id` | UUID FK → users | Nullable |
| `name` | TEXT | Human label |
| `key_hash` | TEXT UNIQUE | bcrypt/sha256 hash — plaintext never stored |
| `last_used_at` | TIMESTAMPTZ | |
| `expires_at` | TIMESTAMPTZ | Nullable = no expiry |
| `created_at` | TIMESTAMPTZ | |

---

## Entity Relationship

```
organizations
    ├── users
    ├── aws_profiles
    └── sessions ──── messages ──── tool_calls
                  │            └── usage_events
                  └── findings
```

## Key Design Decisions

- `sessions.id` is the LangGraph `thread_id` — no join needed to link conversation history to app data.
- `messages.metadata JSONB` stores arbitrary LangChain runtime context (run ID, tags, RunnableConfig extras) without schema changes.
- `tool_calls.error` is a separate TEXT column (not just checking `result.error`) so you can query failed calls with a simple `WHERE error IS NOT NULL`.
- `usage_events.cost_usd` is computed by the app from the pricing map — not trusted from the API.
- `user_id` / `org_id` on sessions are nullable intentionally: the app is fully functional before any auth system is built.
