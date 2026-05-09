# OpenDevOps Agent

Open-source AWS DevOps Agent powered by OpenRouter LLMs. Investigates incidents, finds root causes,
and gives actionable mitigation plans — without the AWS DevOps Agent price tag.

## What's inside

- **LangChain DeepAgents** as the agent framework — planning, tool orchestration, and session memory out of the box
- **21 read-only AWS tools** across CloudWatch (6), CloudTrail (2), ECS (4), Lambda (4), EC2 (2), RDS (2), IAM (1), plus bash escape hatch, cross-session history analytics, skills, and `submit_investigation` — plain Python functions, schemas inferred automatically
- **Sandboxed bash execution tool** — agent can run whitelisted read-only AWS CLI, kubectl, and docker commands as a last resort when the structured tools fall short; every command validated against an allowlist before execution; never uses `shell=True`; hard 30-second timeout
  - Includes **CloudWatch Logs Insights** (`query_logs_insights`) — full query language support: `fields`, `filter`, `stats`, `sort`, `limit`; results include scanned MB
- **Streaming responses** — FastAPI SSE endpoint streams agent tokens in real time as the LLM reasons; tool calls appear as they complete
- **Web UI** — React + Vite SPA served by FastAPI:
  - **Chat page** — streaming responses, collapsible tool call inspector, cost/latency card, stop button
  - **Session history sidebar** — lists all past conversations; click any to resume with full tool call inspector and cost card restored; new chat and delete (soft) buttons
  - **Dashboard** — session counts, tool call stats, cost/latency, context saved, activity chart, service breakdown, root cause distribution, recent sessions
  - **History page** — keyword search across all past sessions
  - **Settings page** — real-time read-only view of active configuration (env vars + agent config) fetched from the backend
  - **Team page** — admin-only user management: add, remove, and change roles
- **Auth & RBAC** — optional password-based auth with `admin` and `user` roles; JWT tokens; first registered user auto-becomes admin; disabled by default (set `JWT_SECRET` to enable) — see [docs/auth.md](docs/auth.md)
- **Three storage backends** — pick one via `CHECKPOINT_BACKEND` in `.env`; see [`docs/databases.md`](docs/databases.md)
  - `memory` — zero config, no persistence; great for CI and quick testing
  - `sqlite` — local file, no external services; recommended for single-server and personal use
  - `postgres` — full production persistence via psycopg3 + `AsyncPostgresSaver`
  - Schema: `users`, `sessions`, `messages`, `tool_calls`, `usage_events` — see [`docs/schema.md`](docs/schema.md)
  - Soft delete — deleted sessions are hidden immediately but data is preserved for the 30-day cleanup job
- **Structured logging** via Loguru — used consistently across all modules (tools, agent, API, CLI); every request shows agent reasoning, tool calls with args/results, and a done summary with latency + token counts
- **CLI** — `devops-agent investigate`, `ask`, and `report` commands powered by the same agent
- **OpenRouter** as the LLM provider — swap models via a single env var, no code changes

## Quick Start

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — add your OPENROUTER_API_KEY and set AWS_PROFILE
```

### 3. Set up AWS profile

```bash
aws configure --profile devops-agent-readonly
# AWS Access Key ID:     your_key_id
# AWS Secret Access Key: your_secret_key
# Default region:        us-east-1
# Default output format: json

# Verify
aws sts get-caller-identity --profile devops-agent-readonly
```

### 4. Choose a storage backend

Three options — pick one and add it to `.env`. Full details in [`docs/databases.md`](docs/databases.md).

**Memory** (default — zero config, nothing persists on restart)
```bash
CHECKPOINT_BACKEND=memory
```

**SQLite** (recommended for local dev — persists to a file, no external service needed)
```bash
CHECKPOINT_BACKEND=sqlite
SQLITE_PATH=./data/agent.db   # created automatically on first start
```

**PostgreSQL** (recommended for production)
```bash
# Start Postgres with Docker
docker run -d --name opendevops-pg \
  -e POSTGRES_DB=opendevops \
  -e POSTGRES_USER=dev \
  -e POSTGRES_PASSWORD=dev \
  -p 5433:5432 \
  postgres:16

# Add to .env
CHECKPOINT_BACKEND=postgres
DATABASE_URL=postgresql://dev:dev@localhost:5433/opendevops

# Create app tables (safe to re-run)
uv run python scripts/setup_db.py
```

### 5. Run

**Option A — Docker Compose (recommended, AWS CLI included)**

```bash
docker compose up --build
# Backend: http://localhost:8000
# Frontend: http://localhost:80
# Postgres (host): localhost:5433
```

The backend image installs AWS CLI v2 automatically — the bash execution tool
works out of the box. Host AWS credentials (`~/.aws`) are mounted read-only
into the container. For production on AWS, remove the volume mount and attach
an IAM role to the instance/task instead.

**Option B — Local dev (two terminals)**

```bash
# Terminal 1 — FastAPI backend
uv run uvicorn api.app:app --reload
```

```bash
# Terminal 2 — React frontend (Vite dev server with HMR)
cd frontend
npm run dev
# Open http://localhost:5173
```

> **Note:** local dev requires `aws` CLI installed on your machine for the bash
> tool to work. Install it from https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html

**CLI**

```bash
# Investigate an incident
uv run devops-agent investigate "high error rate on my payment Lambda"

# With alarm and service hints
uv run devops-agent investigate "latency spike" --alarm HighLatencyAlarm --service api-service

# Freeform Q&A
uv run devops-agent ask "why would a Lambda function suddenly start throttling?"

# Daily ops health report
uv run devops-agent report
```

## AWS IAM Setup

Attach `iam-policy.json` to the IAM user or role your agent uses. It grants read-only access
to CloudWatch, CloudTrail, ECS, Lambda, EC2, RDS, and IAM.

```bash
aws iam create-policy \
  --policy-name OpenDevOpsAgentReadOnly \
  --policy-document file://iam-policy.json
```

## Project Structure

```
src/
├── agent/             # DeepAgents setup, prompts, models, config, DB layer
├── tools/             # 19 read-only AWS tool functions
├── api/
│   ├── app.py         # FastAPI app factory — mounts routers, serves frontend
│   ├── auth.py        # JWT helpers + FastAPI auth dependencies
│   └── routers/
│       ├── auth.py    # POST /auth/register|login · GET /auth/status|me
│       ├── chat.py    # POST /chat — SSE streaming endpoint
│       ├── sessions.py# GET/DELETE /sessions — session history
│       ├── users.py   # GET/POST/PATCH/DELETE /users (admin only)
│       ├── settings.py# GET /settings — read-only config view
│       ├── history.py # GET /history/* — cross-session analytics
│       └── dashboard.py# GET /stats
├── cli/               # Typer CLI commands
├── config/
│   └── appsettings.py # Pydantic Settings — single source of truth for all env vars
├── models/            # Pydantic models: agent, chat, sessions, users
├── skills/            # Markdown runbooks (lambda-throttling + add your own)
└── integrations/
    └── slack_webhook.py
frontend/
└── src/
    ├── pages/         # ChatPage, DashboardPage, HistoryPage, SettingsPage, UsersPage, LoginPage
    └── components/    # Sidebar, Header, ProtectedRoute, AgentMessage, ...
migrations/
├── 001_initial.sql    # Base schema
├── 002_soft_delete.sql
├── 003_usage_events_metadata.sql
└── 004_users_rbac.sql # password_hash + role on users
docs/                  # Feature reference — auth, schema, skills, databases, UI, ...
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `LLM_MODEL` | `openrouter/openai/gpt-4o` | LiteLLM model string — `provider/model` format; see [docs/llm_providers.md](docs/llm_providers.md) |
| `LLM_API_BASE` | none | Custom base URL for OpenAI-compatible endpoints (e.g. Ollama, vLLM) |
| `LLM_API_KEY` | none | API key for custom endpoints; standard provider keys (e.g. `ANTHROPIC_API_KEY`) are read automatically |
| `OPENROUTER_API_KEY` | none | Required when using any `openrouter/` model |
| `CHECKPOINT_BACKEND` | `memory` | Storage backend: `memory` · `sqlite` · `postgres` — see [docs/databases.md](docs/databases.md) |
| `SQLITE_PATH` | `./data/agent.db` | SQLite file path — only used when `CHECKPOINT_BACKEND=sqlite` |
| `DATABASE_URL` | none | PostgreSQL connection string — only used when `CHECKPOINT_BACKEND=postgres` |
| `AWS_REGION` | `us-east-1` | AWS region |
| `AWS_PROFILE` | none | AWS named profile (e.g. `devops-agent-readonly`) |
| `MAX_TOOL_CALLS` | `20` | Hard cap on tool calls per investigation |
| `INVESTIGATION_TIMEOUT` | `120` | Timeout in seconds |
| `TOOL_RESPONSE_MAX_CHARS` | `40000` | Truncate tool responses larger than this before feeding to the LLM; `0` disables |
| `SLACK_WEBHOOK_URL` | none | Slack incoming webhook URL; leave unset to disable notifications |
| `POLL_INTERVAL_MINUTES` | `0` | Proactive polling interval in minutes; `0` disables the poller |
| `POLL_ERROR_THRESHOLD` | `5.0` | Lambda error rate % that triggers an automatic investigation |
| `POLL_REINVESTIGATE_HOURS` | `1` | Cooldown period — skip re-investigating the same alarm within N hours |
| `SUMMARIZATION_ENABLED` | `true` | Auto-compact sessions when they exceed the threshold |
| `SUMMARIZATION_THRESHOLD_CHARS` | `60000` | Total session chars before compaction fires (~15K tokens) |
| `SUMMARIZATION_KEEP_CHARS` | `20000` | Recent chars to preserve intact during compaction (~5K tokens) |
| `JWT_SECRET` | none | Secret key for JWT signing; leave unset to disable auth entirely |
| `JWT_EXPIRE_MINUTES` | `1440` | JWT token lifetime in minutes (default 24 h) |

## TODO / Roadmap

### Near-term
- [x] **Cache layer** — in-process TTL cache (`cachetools`) on all 19 AWS tool functions; 2-minute TTL, 256 entry max, AWS profile+region included in cache key
- [x] **Schema / models layer** — centralized `src/models/` package for all Pydantic models: agent domain, memory state, and API request/response schemas
- [ ] **Soft-deleted session cleanup job** — product version only; OSS users manage their own DB
- [x] **Investigation history skill** — cross-session analysis: recurring errors, most-triggered alarms, patterns across all past sessions for a user
- [x] **User roles** — `admin` / `user` roles with JWT auth, first-user bootstrap, admin-only user management UI; optional (disabled when `JWT_SECRET` unset) — see [docs/auth.md](docs/auth.md)

### Medium-term
- [x] **React frontend** — rewrite the single-file HTML UI in React; component-based architecture, proper state management, hot reload
- [x] **Dashboard** — summarized view of troubleshooting activity, recurring incidents, query breakdown by service
- [x] **Multi-provider LLM support** — 100+ providers via LiteLLM; swap models with a single `LLM_MODEL` env var change; supports OpenRouter, Anthropic, OpenAI, Groq, Ollama, and any OpenAI-compatible endpoint; see [docs/llm_providers.md](docs/llm_providers.md)
- [x] **MCP integration** — expose the agent as an MCP server (`devops-agent mcp`); `investigate`, `ask`, and `list_sessions` tools available in Claude Desktop, Cursor, or any MCP-compatible client; stdio and HTTP+SSE transports; see [docs/mcp_server.md](docs/mcp_server.md)
- [x] **Multi-backend storage** — `memory` (zero config), `sqlite` (local file, no external service), `postgres` (production); switch with one env var; see [docs/databases.md](docs/databases.md)
- [x] **Skills system** — on-demand investigation skills loaded from `src/skills/*/SKILL.md`; skill names injected into system prompt at startup, full content loaded only when agent calls `use_skill(name)`; ships with `lambda-throttling` skill; add your own by dropping a `SKILL.md` into `src/skills/<name>/`
- [ ] **Custom tools via URL** — register external tools by pointing at an OpenAPI/HTTP endpoint; agent discovers and calls them alongside built-in AWS tools
- [x] **Bash CLI escape hatch (Phase 1)** — `run_bash_command` is implemented for read-only AWS CLI, kubectl, and docker commands with strict allowlist validation and timeout.
- [ ] **Bash sandbox Phase 2** — run each bash command in an isolated throwaway container (`--network none`, read-only FS, non-root, resource limits).
- [x] **Tool response capping** — truncates oversized AWS tool responses (CloudWatch logs, CloudTrail events) before they reach the LLM context window; configurable via `TOOL_RESPONSE_MAX_CHARS` (default 40 000 chars ≈ 10 K tokens)
- [x] **Conversation summarization** — automatically summarize old messages when the session approaches the model's context limit; preserves recent exchanges and injects a structured summary so long investigations never fail mid-session; summarization events tracked in `usage_events.metadata` and surfaced in the dashboard
- [ ] **Optimize tool loading** — pass only relevant tools per investigation context instead of the full 19-tool set
- [ ] **Message middleware pipeline** — compaction, summarization, intent detection, context trimmer
- [ ] **Guardrails** — input/output validation, PII scrubbing, query scope enforcement
- [ ] **Multi-model escalation** — route simple queries to cheaper/smaller models, escalate hard investigations to larger ones
- [x] **Fun streaming labels** — contextual loading copy ("Digging through CloudTrail…", "Lemonizing metrics…", "Cooking up a root cause…")
- [x] **Slack notifications** — reactive: posts a color-coded Block Kit message to a Slack webhook after every investigation; proactive: background poller checks CloudWatch alarms and Lambda error rates on a configurable interval, auto-investigates new anomalies, and posts findings without any human trigger; set `SLACK_WEBHOOK_URL` and `POLL_INTERVAL_MINUTES` in `.env` to enable

### Later
- [ ] **Observability** — OpenTelemetry traces for agent steps, tool call latency, LLM token usage
- [ ] **Follow-up question suggestions** — after each investigation completes, generate 3 suggested follow-up questions in the background and surface them in the UI as clickable chips
- [ ] **Session / user feedback loop** — thumbs up/down on investigations, feed signals back to the agent and to an internal quality dashboard
- [ ] **Telegram integration** — bot that accepts `/investigate` commands and streams findings back to a chat or group
- [ ] **Knowledge base** — attach internal runbooks, post-mortems, and architecture docs so the agent grounds answers in org-specific context
- [ ] **Multi-account AWS** — support multiple AWS profiles per org via `aws_profiles` table (schema already in place)
- [ ] **Multi-cloud support** — extend tooling to GCP (Cloud Monitoring, Cloud Logging, GKE) and Azure (Monitor, Log Analytics, AKS); unified incident investigation across providers
- [ ] **Bash sandbox Phase 2 — isolated Docker container** — each `run_bash_command` call runs inside a throwaway container: `--network none`, `--read-only` filesystem, `--memory 256m`, `--cpus 0.5`, non-root user; container destroyed immediately after the command completes; IAM read-only role remains the last line of defense

### Product (SaaS)
- [ ] **Redis cache** — replace in-process `cachetools` with Redis; shared across workers, survives restarts, per-org cache namespacing to prevent data leakage between tenants
- [ ] **Soft-deleted session cleanup** — scheduled job (Inngest or APScheduler) to purge `is_deleted = TRUE` sessions older than a configurable retention window (default 30 days); GDPR right-to-erasure compliance
- [ ] **Org-scoped AWS credential management** — per-org credential vault; agents use org-scoped profiles instead of a single global `AWS_PROFILE`
- [ ] **Per-org AWS credential store** — encrypted credential vault per organization; agents use org-scoped profiles instead of a single global `AWS_PROFILE`
- [ ] **Billing & usage metering** — track token usage and tool calls per org/user; expose cost dashboards; integrate with Stripe for usage-based billing

## Security & Sandboxing

The bash execution tool runs whitelisted read-only commands only.
Every command is validated against an allowlist before execution —
anything not on the list is rejected immediately and logged.

**Current (Phase 1):** allowlist validation + subprocess with hard timeout.
No write commands permitted under any circumstances. `shell=True` is never used.

**Phase 2 — Isolated sandbox (planned):**
- Every bash command runs inside a throwaway Docker container
- `--network none` — no internet access from inside the sandbox
- `--read-only` filesystem — container cannot write to disk
- `--memory 256m` and `--cpus 0.5` — resource caps
- Non-root user inside the container
- Container is destroyed immediately after the command completes
- Even if the LLM misbehaves, the IAM read-only role is the last line of defense

The agent never executes fixes automatically. It investigates, suggests,
and waits for human approval before anything changes.

## Development

```bash
# Run tests
uv run pytest

# Lint + format
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```
