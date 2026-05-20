# Databases

OpenDevOps Agent supports three storage backends. Pick one per deployment — set
`CHECKPOINT_BACKEND` in your `.env` and you're done.

---

## Quick reference

| Backend    | Persistence | External service | Dashboard | Best for                          |
|------------|-------------|-----------------|-----------|-----------------------------------|
| `memory`   | None        | None            | Counts only; no autonomous monitoring | CI, quick demos, local testing  |
| `sqlite`   | Local file  | None            | Full      | Single-server, personal use       |
| `postgres` | Database    | PostgreSQL 14+  | Full      | Production, teams, multi-instance |

---

## `memory` — zero config, no persistence

```bash
CHECKPOINT_BACKEND=memory
```

Everything lives in Python dicts for the life of the process. On restart, all
sessions and history are gone. The LangGraph checkpointer uses `MemorySaver`.

Autonomous monitoring is disabled in memory mode. The poller and SQS event
consumer require durable incident claims, so use SQLite or PostgreSQL for those
features.

**When to use:** CI pipelines, smoke-testing, one-off demos.

> **Dashboard limitation:** summary counts (sessions, queries, tool calls, cost) update
> correctly, but all charts and lists — activity by day, top tools, recent sessions,
> root causes — are always empty. This is by design. Switch to `sqlite` or `postgres`
> if you need a working dashboard.

---

## `sqlite` — local file, zero dependencies

```bash
CHECKPOINT_BACKEND=sqlite
SQLITE_PATH=./data/agent.db   # default, relative to CWD
```

Uses `aiosqlite` for the app tables and `langgraph-checkpoint-sqlite` for the
LangGraph checkpointer. Both share the same `.db` file via separate connections
with WAL mode enabled.

SQLite also stores app-level configuration such as init wizard completion and event
monitoring infrastructure state in `app_config`.

The file and its parent directory are created automatically on first start.

**When to use:** Single-server deployments, personal use, hobbyist setups where
you want persistence without running a database.

**Limitations:**
- Single writer at a time (fine for one server process)
- `LIKE` search is ASCII case-insensitive only (vs PostgreSQL's `ILIKE`)
- History analytics use `json_extract()` (requires SQLite ≥ 3.38, released 2022)

### Docker with SQLite

Mount a host directory so the database survives container restarts:

```yaml
# docker-compose.yml
services:
  backend:
    environment:
      CHECKPOINT_BACKEND: sqlite
      SQLITE_PATH: /data/agent.db
    volumes:
      - ./data:/data
```

---

## `postgres` — production

```bash
CHECKPOINT_BACKEND=postgres
DATABASE_URL=postgresql://user:password@localhost:5432/opendevops
```

Uses `psycopg3` + `AsyncConnectionPool` for the app tables and
`langgraph-checkpoint-postgres` for the LangGraph checkpointer.
The checkpointer schema is created automatically via `AsyncPostgresSaver.setup()`.
Init wizard and event-infrastructure state are stored in the `app_config` table so
all app instances share the same setup status.

**When to use:** Production deployments, team environments, when you need full
dashboard analytics, multi-instance horizontal scaling.

**Requirements:** PostgreSQL 14+ (uses `DISTINCT ON`, `FILTER (WHERE ...)`,
`DATE_TRUNC`, `INTERVAL` arithmetic).

### Schema setup

SQLite and memory create their tables automatically. **PostgreSQL requires a
one-time migration script:**

```bash
uv run python scripts/setup_db.py
```

This applies all files in `migrations/` in order and initialises the LangGraph
checkpointer tables. Safe to re-run — all statements use `IF NOT EXISTS`. The
LangGraph checkpoint tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`)
are created automatically by the script; do not add them to `migrations/`.

### Connection poolers (PgBouncer / Supabase)

The pool is opened with `prepare_threshold=None` to disable psycopg3
auto-prepared statements, which are incompatible with transaction-mode poolers.

---

## Migrating between backends

There is no automatic migration tool. The backends are independent storage
systems. If you start on `sqlite` and later move to `postgres`:

1. Export your sessions with the API (`GET /sessions`) before switching.
2. Change `CHECKPOINT_BACKEND=postgres` and provide `DATABASE_URL`.
3. Historical sessions from SQLite are not carried over — start fresh.

For most users, the history is short enough that starting fresh is acceptable.

---

## Adding a new backend

1. Create `src/agent/db/my_backend.py` implementing `DatabaseBackend` (see `base.py`).
2. Add a branch to `_create_backend()` in `src/agent/db/__init__.py`.
3. Document it here.
