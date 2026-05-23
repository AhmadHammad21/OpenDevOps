# CLAUDE.md — OpenDevOps Agent

## Project Overview

OpenDevOps Agent is an open-source AWS incident investigation tool powered by any LLM via LiteLLM. It runs a LangGraph ReAct loop (via DeepAgents) that calls 27 tools — 21 structured boto3 AWS tools plus bash, history analytics, skills, and a structured final-answer tool — then streams results to a React/Vite chat UI over SSE. Auth, multi-user RBAC, event-driven incident detection (EventBridge → SQS), and proactive anomaly polling are all built in and optional.

---

## Repo Structure

```
apps/
  backend/        Python backend — src/, migrations/, tests/, scripts/, pyproject.toml
  frontend/       React/Vite UI — src/, package.json, vite.config.ts
  documentation/  Markdown docs (future hosted docs site)
deployment/
  docker-compose/ docker-compose.yml (PostgreSQL + backend + frontend)
  railway/        Dockerfile.railway + railway.toml (combined single-image deploy)
design-system/   Cross-cutting design reference (colors, typography, UI kits)
demos/           Reproducible AWS incident scripts for local testing
Makefile         Root convenience targets — wraps `cd apps/backend && uv run ...`
```

All Python commands run from `apps/backend/` (or via `make <target>` at repo root).

---

## Automatic Behavior Rules

**Always do these when making changes:**

- **New env var:** add to both `apps/backend/src/config/appsettings.py` (source of truth, Pydantic field with default) AND `.env.example` (with a comment). Never read env vars directly — always go through `settings`.
- **New DB column or table:** create a new numbered migration in `apps/backend/migrations/` (e.g. `006_name.sql`). Never add columns inline in Python code.
- **New tool:** add it to `ALL_TOOLS` in `apps/backend/src/agent/core.py`. Tool functions must be plain synchronous Python functions — DeepAgents infers the JSON schema from type hints and docstrings.
- **New API route that matches a React Router path:** prefix it with `/api/` to avoid the SPA fallback conflict. The `/{full_path:path}` catch-all in `app.py` intercepts any GET that matches a registered FastAPI route first.
- **New skill:** drop a `SKILL.md` file into `apps/backend/src/skills/<name>/SKILL.md`. It is picked up automatically at startup — no code changes needed. Use the frontmatter format (`name`, `description`) from the existing `lambda-throttling` skill.
- **Docs sync:** if a feature has a corresponding file in `apps/documentation/`, update it when the feature changes. The `apps/documentation/` folder is the public documentation source.

---

## Common Commands

```bash
# Install / update dependencies
cd apps/backend && uv sync          # or: make install

# Development server — FastAPI with hot reload
cd apps/backend && uv run dev       # or: make dev

# Production web UI (FastAPI backend + serves built frontend, no reload)
cd apps/backend && uv run devops-agent ui   # or: make ui

# Apply SQL migrations to PostgreSQL (requires CHECKPOINT_BACKEND=postgres + DATABASE_URL)
cd apps/backend && uv run migrate   # or: make migrate

# CLI investigation
cd apps/backend && uv run devops-agent investigate "Lambda high error rate on payment service"
cd apps/backend && uv run devops-agent ask "Why would an ECS task OOM?"
cd apps/backend && uv run devops-agent report --days 7

# MCP server
cd apps/backend && uv run devops-agent mcp              # stdio transport (Claude Desktop, Cursor)
cd apps/backend && uv run devops-agent mcp --http       # HTTP+SSE transport, port 8001

# Tests
cd apps/backend && uv run pytest    # or: make test

# Lint / format
cd apps/backend && uv run ruff check src/
cd apps/backend && uv run ruff format src/   # or: make lint / make lint-fix

# Full stack with PostgreSQL (Docker Compose)
docker compose -f deployment/docker-compose/docker-compose.yml up --build   # or: make compose-up

# Frontend dev server (port 5173, proxies API to localhost:8000)
cd apps/frontend && npm install && npm run dev   # or: make frontend-dev

# Frontend production build (output to apps/frontend/dist/ — served by FastAPI)
cd apps/frontend && npm run build   # or: make frontend-build
```

---

## Current State

Everything below is built and working in the codebase:

### Agent & Tools
- **Framework:** DeepAgents (`create_deep_agent`) wrapping a LangGraph ReAct loop. `ChatLiteLLM` as the model interface — supports OpenRouter, Anthropic, OpenAI, Groq, Ollama, and any OpenAI-compatible endpoint via a single `LLM_MODEL` env var.
- **27 tools total** registered in `ALL_TOOLS` in `apps/backend/src/agent/core.py`:
  - CloudWatch (6): `get_alarms`, `get_alarm_history`, `get_metric_data`, `get_log_events`, `describe_log_groups`, `query_logs_insights`
  - CloudTrail (2): trail events + event lookup
  - ECS (4): clusters, services, service detail, tasks
  - Lambda (4): list, config, error rate, concurrent executions
  - EC2 (2): list instances, instance details
  - RDS (2): list DBs, DB details
  - IAM (1): describe role + policies
  - Bash (1): `run_bash_command` — allowlisted read-only `aws`, `kubectl`, `docker` commands; never `shell=True`; 30s hard timeout
  - History (2): `get_investigation_history`, `search_past_investigations`
  - Skills (2): `list_skills`, `use_skill`
  - Final answer (1): `submit_investigation` — structured output required to end every investigation
- **Tool response capping:** `with_cap()` wraps every tool at startup when `TOOL_RESPONSE_MAX_CHARS > 0`; truncates oversized responses and appends a notice to the LLM.
- **Tool caching:** `@tool_cached` — in-process TTL LRU cache (2-min TTL, 256 entries max); cache key includes function name + AWS profile + region.
- **Skills system:** one skill ships (`lambda-throttling`). The system prompt is built at import time by scanning `apps/backend/src/skills/*/SKILL.md` — skill names are injected; full content is loaded lazily when the agent calls `use_skill(name)`.
- **Summarization:** `maybe_summarize()` runs before each agent call; compacts old messages when total chars exceed `SUMMARIZATION_THRESHOLD_CHARS`; tracks the event in `usage_events` with `metadata.summarization=True`.
- **Cancellation:** `DELETE /chat/{session_id}` sets an `asyncio.Event` that stops the streaming loop at the next chunk boundary.

### Storage
- Three backends all implementing `DatabaseBackend` ABC: `memory` (default, zero config), `sqlite` (aiosqlite + LangGraph SQLite checkpointer), `postgres` (psycopg3 async + `AsyncPostgresSaver`).
- LangGraph checkpointer tables are created automatically by `AsyncPostgresSaver.setup()`. Application tables come from `migrations/001–005_*.sql`.
- Schema tables: `organizations`, `users`, `aws_profiles`, `sessions`, `messages`, `tool_calls`, `usage_events`, `findings`, `api_keys`, `alerts`.
- Soft delete is in place on sessions (`is_deleted`, `deleted_at` from migration 002).

### API
- FastAPI SSE endpoint at `POST /chat`; streams `token`, `tool_status`, `tool_call`, `error`, `done`, `cancelled` events.
- SPA fallback: `GET /{full_path:path}` returns `apps/frontend/dist/index.html` so React Router works on refresh.
- All routes that could conflict with React Router paths use the `/api/` prefix: `/api/settings`, `/api/users`, `/api/history`, `/api/monitoring`, `/api/init`.
- Auth: optional JWT (HS256 via python-jose + bcrypt). Disabled when `JWT_SECRET` is unset — `get_current_user()` returns `None` in that case, meaning all routes are public.

### Event-Driven Detection
- `event_consumer_loop()` long-polls SQS (20s wait), processes EventBridge events (CloudWatch alarm, ECS task failure, Lambda async error, RDS event, EC2 state change, CodePipeline failure, AWS Health), runs a full agent investigation per event, delivers results to SNS + Slack, persists to `alerts` table.
- `context_collectors.collect_context()` pre-fetches resource facts deterministically before the LLM runs to reduce tool call count.
- Starts automatically on app startup if `event_consumer_enabled=True`, `sqs_queue_url` is set, or database-backed app config marks event infrastructure as enabled. Autonomous monitoring requires SQLite or PostgreSQL; memory mode is disabled for poller/consumer runs.

### Proactive Polling
- `polling_loop()` runs every `POLL_INTERVAL_SECONDS` seconds (disabled by default at 0); checks CloudWatch alarms in ALARM state and Lambda error rates above `POLL_ERROR_THRESHOLD`; auto-investigates new anomalies and posts to Slack/Telegram. Dedup uses canonical incident keys and durable DB-backed claims.

### Frontend
- React 18 + TypeScript + Vite + Tailwind CSS + `@tailwindcss/typography`
- Font: Inter Variable (Google Fonts) with a full system fallback stack
- Routes: `/`, `/chat/:sessionId`, `/dashboard`, `/monitoring`, `/monitoring/:alertId`, `/history`, `/settings`, `/users`, `/login`
- Chat page: SSE streaming, tool call inspector, cost/latency card, stop button, suggestion chips on empty state, `?prompt=` deeplink support
- Sidebar: paginated session list (15 at a time), three-dot menu with rename + delete (portal-based, no overflow clipping), real `<a>` links for native right-click
- Settings: Environment, Agent Config, Integrations (UI stubs), AWS Configuration (editable, admin only), Preferences (dark mode)

### Auth & MCP
- RBAC: `admin` and `user` roles. First registered user auto-becomes admin. `JWT_SECRET` unset = auth disabled.
- MCP server via fastmcp: `investigate`, `ask`, `list_sessions` tools. Stdio and HTTP+SSE transports.

---

## Current Priorities

Incomplete items from the README roadmap (do not mark complete here — update README when done):

- **Custom tools via URL** — register external tools by OpenAPI endpoint; agent discovers them alongside built-in tools
- **Bash sandbox Phase 2** — throwaway Docker container per command: `--network none`, read-only FS, non-root, `--memory 256m`, killed immediately after; current Phase 1 (subprocess allowlist) is in `apps/backend/src/tools/bash_tool.py`
- **Optimize tool loading** — pass only contextually relevant tools instead of the full 27-tool set per invocation
- **OpenTelemetry traces** — spans for agent steps, tool call latency, token usage; OTLP export
- **Follow-up question suggestions** — add `follow_up_questions: list[str]` to `submit_investigation` schema (same call, no extra LLM cost); surface as chips in the chat UI after investigation completes
- **Session / user feedback loop** — thumbs up/down on investigations; `feedback` column in `usage_events` (needs migration 006)
- **Slack Integration UI** — Slack backend is fully implemented (`apps/backend/src/integrations/slack_webhook.py`); Settings → Integrations "Connect" button is currently a non-functional stub
- **Session rename** — `PATCH /sessions/{id}` + inline edit in sidebar three-dot menu
- **Multi-account AWS** — `aws_profiles` table already in schema; needs Settings UI + per-session profile selector
- **Knowledge base** — attach runbooks, post-mortems, architecture docs beyond the skills system

---

## What NOT to Change Without Discussion

| Contract | Why it matters |
|---|---|
| **SSE event types:** `token`, `tool_status`, `tool_call`, `error`, `done`, `cancelled` | Frontend `ChatPage.tsx` switches on these exact strings. Renaming or adding new required fields is a breaking change. |
| **Tool function signatures** | DeepAgents infers JSON schema from Python type hints + docstrings. Adding `*args`, `**kwargs`, removing type hints, or making parameters non-primitive breaks schema inference silently. |
| **`DatabaseBackend` ABC** (`apps/backend/src/agent/db/base.py`) | All three backends must implement the same interface. Adding a method requires implementing it in all three backends plus `memory.py` defaults. |
| **LangGraph checkpointer wiring** | The checkpointer is passed into `create_deep_agent()` and drives session continuity via `thread_id = session_id`. Do not write messages to the DB outside `save_*` calls or bypass the checkpointer. |
| **Agent framework (DeepAgents + LangGraph)** | The ReAct loop, tool dispatch, checkpointing, and `recursion_limit` contract all depend on this. Do not swap. |
| **DB schema migrations** | Tables have a defined shape. New columns need a new file in `migrations/`. Never add columns inline in Python or modify existing migration files. |
| **Auth opt-out pattern** | `get_current_user()` returns `None` when `jwt_secret` is unset (dev/memory mode). New routes that call `Depends(get_current_user)` must handle `None` gracefully — do not hard-require auth in non-admin routes. |
| **psycopg3 placeholder syntax** | psycopg3 uses `%s` (not `$1`/`$2`). Using asyncpg-style params causes silent failures with no Python exception. |

---

## Tech Stack

| Layer | Library / Version |
|---|---|
| Language | Python 3.11+ |
| Agent framework | `deepagents` + `langgraph>=0.2.0` |
| LLM abstraction | `litellm>=1.83.0` via `langchain-litellm` (`ChatLiteLLM`) |
| AWS SDK | `boto3>=1.34.0` (sync; all tools are synchronous) |
| Web backend | `fastapi>=0.111.0` + `uvicorn>=0.30.0` |
| CLI | `typer>=0.12.0` + `rich>=13.7.0` |
| Config | `pydantic-settings>=2.3.0` + `pydantic>=2.7.0` |
| Storage | `aiosqlite>=0.20.0` / `psycopg[binary,pool]>=3.1.0` + LangGraph checkpointers |
| Auth | `python-jose[cryptography]>=3.3.0` + `bcrypt>=5.0.0` |
| MCP server | `fastmcp>=3.2.4` |
| Tool cache | `cachetools>=5.3.0` (TTLCache, in-process) |
| Logging | `loguru>=0.7.0` (never `print`) |
| HTTP client | `httpx>=0.27.0` |
| Testing | `pytest>=8.0.0`, `pytest-asyncio>=0.23.0`, `moto>=5.0.0`, `pytest-mock>=3.14.0` |
| Linting | `ruff>=0.4.0` (line-length 100, Python 3.11 target, `asyncio_mode = "auto"`) |
| Package manager | **uv** — always `uv run` and `uv add`, never bare `pip` |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS 3, `@tailwindcss/typography` |
| Font | Inter Variable (Google Fonts) — full system fallback stack in `apps/frontend/tailwind.config.js` |

---

## Environment Variables

All read from `apps/backend/src/config/appsettings.py` (Pydantic Settings — single source of truth). `.env.example` mirrors every variable.

```bash
# LLM — LiteLLM model string format
LLM_MODEL=openrouter/openai/gpt-4o     # default
LLM_API_BASE=                          # optional custom base URL
LLM_API_KEY=                           # optional custom API key
OPENROUTER_API_KEY=                    # used when LLM_MODEL starts with "openrouter/"

# AWS
AWS_REGION=us-east-1                   # default
AWS_PROFILE=                           # optional named ~/.aws profile

# Agent behavior
MAX_TOOL_CALLS=20                      # recursion_limit = MAX_TOOL_CALLS * 3 + 15
INVESTIGATION_TIMEOUT=120              # seconds before asyncio.TimeoutError
LOG_LEVEL=INFO
LOG_CONSOLE_ENABLED=true               # false = suppress all console output
LOG_CONSOLE_COLORIZE=true              # false = strip ANSI colours (CI / Docker)
TOOL_RESPONSE_MAX_CHARS=40000          # 0 = disabled; ~10K tokens at 4 chars/token

# Storage backend — pick exactly one
CHECKPOINT_BACKEND=memory              # memory | sqlite | postgres
SQLITE_PATH=./data/agent.db            # only when backend=sqlite
DATABASE_URL=                          # only when backend=postgres (psycopg3 DSN)

# Conversation summarization
SUMMARIZATION_ENABLED=true
SUMMARIZATION_THRESHOLD_CHARS=60000   # trigger when session exceeds this (~15K tokens)
SUMMARIZATION_KEEP_CHARS=20000        # preserve this many recent chars intact (~5K tokens)

# Auth — leave unset to disable entirely (all routes public)
JWT_SECRET=                            # set to enable auth; required for /api/users
JWT_EXPIRE_MINUTES=1440                # 24 hours

# Slack notifications
SLACK_WEBHOOK_URL=                     # leave unset to disable

# Proactive polling
POLL_INTERVAL_SECONDS=0               # 0 = disabled; set to e.g. 300 (5 min) to enable
POLL_ERROR_THRESHOLD=5.0              # Lambda error rate % to trigger investigation
POLL_REINVESTIGATE_HOURS=1            # dedup window

# Event-driven detection
SNS_TOPIC_ARN=                         # SNS publish target after investigations
SQS_QUEUE_URL=                         # SQS queue for EventBridge events
EVENT_CONSUMER_ENABLED=false           # also auto-starts if SQS_QUEUE_URL is set or app config enables infra

# Misc
DATA_DIR=data                          # reserved for future file-based state
```

---

## Core Architecture

### Request flow (web chat)
```
POST /chat  →  maybe_summarize()  →  agent.astream()
  LangGraph ReAct loop:
    LLM reasons  →  picks tool  →  @tool_cached check  →  with_cap()  →  boto3 / subprocess
    result injected back to LLM  →  repeat until submit_investigation() or MAX_TOOL_CALLS
  SSE events streamed per chunk:
    token  |  tool_status  |  tool_call  |  error  |  done  |  cancelled
  After stream ends:
    save_turn()  →  upsert_session + save_message + save_tool_calls + save_usage_event
    notify_slack()  →  only if submit_investigation was called
```

### Event-driven flow
```
EventBridge rules (9 event types)
  →  SQS queue  →  event_consumer_loop() (long-poll, 20s wait)
    →  _is_real_failure() filter
    →  collect_context() (deterministic boto3 pre-fetch, no LLM)
    →  agent.ainvoke() (full ReAct loop)
    →  _deliver(): SNS publish + Slack post + add_alert() → alerts table
```

### Startup sequence
```
db.init()  →  init_agent(checkpointer)
  optional: asyncio.create_task(polling_loop())       if POLL_INTERVAL_SECONDS > 0
  optional: asyncio.create_task(event_consumer_loop()) if SQS configured or app config enables infra
```

### Session continuity
The LangGraph checkpointer stores full thread state keyed by `session_id`. Every `/chat` call resumes the thread by passing `thread_id = session_id` in config — the agent sees complete history without the API explicitly passing messages.

---

## Code Style Rules

- **Type hints everywhere** — no untyped functions, no `Any` without import
- **Tool functions are synchronous** — boto3 is sync; `async` lives only in the API and DB layers
- **Tools always return `dict`, never raise** — catch `BotoCoreError`, `ClientError`, and `Exception`; return `{"error": str(e), ...}` with safe empty defaults
- **Never use `shell=True`** in subprocess — `bash_tool.py` uses `shlex.split()` + list-form `subprocess.run()`
- **Credentials via env or AWS profiles only** — never hardcoded, never in source
- **`logger` (Loguru) for all output** — never `print()`
- **`uv run` / `uv add`** — never bare `pip install`
- **ruff** for lint and format — `line-length = 100`, `target-version = "py311"`, rules `E F I UP`
- **psycopg3 uses `%s` placeholders** — not `$1`/`$2` (that is asyncpg)
- **Route prefix rule** — any API route whose path matches a React Router path must use `/api/` prefix to avoid the SPA fallback catch-all intercepting browser GETs on refresh
- **Migrations are append-only** — never modify existing `.sql` files; add a new numbered file
- **No `shell=True`, no write commands in bash tool** — the allowlist is the contract; never bypass it
