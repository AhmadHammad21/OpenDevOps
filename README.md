# OpenDevOps Agent

Open-source AWS DevOps Agent powered by OpenRouter LLMs. Investigates incidents, finds root causes,
and gives actionable mitigation plans — without the AWS DevOps Agent price tag.

## What's inside

- **LangChain DeepAgents** as the agent framework — planning, tool orchestration, and session memory out of the box
- **19 read-only AWS tools** across CloudWatch, CloudTrail, ECS, Lambda, EC2, RDS, and IAM — plain Python functions, schemas inferred automatically
  - Includes **CloudWatch Logs Insights** (`query_logs_insights`) — full query language support: `fields`, `filter`, `stats`, `sort`, `limit`; results include scanned MB
- **Streaming responses** — FastAPI SSE endpoint streams agent tokens in real time as the LLM reasons; tool calls appear as they complete
- **Web UI** — FastAPI backend with a chat interface that shows:
  - **Session history sidebar** — lists all past conversations; click any to resume with full tool call inspector and cost card restored; new chat and delete (soft) buttons
  - Live tool calls (name, args, result) — collapsible, closed by default
  - **Cost tracking card** — input/output tokens, per-component USD cost, total cost, latency — collapsible, closed by default
  - Pricing map for `google/gemma-4-26b-a4b-it`, `anthropic/claude-3.5-sonnet`, `openai/gpt-4o` (extend as needed)
  - Stop button cancels an in-flight request mid-stream
- **PostgreSQL persistence** (optional) — full conversation history and tool call logs stored in Postgres via psycopg3; falls back to in-memory when `DATABASE_URL` is unset
  - **LangGraph `AsyncPostgresSaver` checkpointer** — agent reasoning state persists across server restarts; resuming a session picks up the full conversation context, not just display messages
  - Schema: `sessions`, `messages`, `tool_calls`, `usage_events` — see [`docs/schema.md`](docs/schema.md)
  - Soft delete — deleted sessions are hidden immediately but data is preserved for the 30-day cleanup job
  - One-shot setup script: `uv run python scripts/setup_db.py` (runs all migrations in order)
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

### 4. Set up the database (optional but recommended)

Without a database the agent still works, using in-memory storage that resets on restart.
For persistent conversation history across restarts, set up PostgreSQL:

```bash
# Start Postgres with Docker
docker run -d --name opendevops-pg \
  -e POSTGRES_DB=opendevops \
  -e POSTGRES_USER=dev \
  -e POSTGRES_PASSWORD=dev \
  -p 5432:5432 \
  postgres:16

# Add to .env
echo "DATABASE_URL=postgresql://dev:dev@localhost:5432/opendevops" >> .env

# Create tables (safe to re-run)
uv run python scripts/setup_db.py
```

The script creates all app tables (`sessions`, `messages`, `tool_calls`, `usage_events`, etc.)
and the LangGraph checkpointer tables in one shot. See [`docs/schema.md`](docs/schema.md) for
the full schema reference.

### 5. Run

**Web UI**

```bash
uv run uvicorn src.api.app:app --reload
# Open http://localhost:8000
```

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
│   └── routers/
│       ├── chat.py    # POST /chat — SSE streaming endpoint
│       └── sessions.py# GET/DELETE /sessions — session history
├── cli/               # Typer CLI commands
└── integrations/      # Future: Slack, PagerDuty
frontend/
└── index.html         # Chat UI — sidebar, live tool calls, cost card
migrations/
└── 001_initial.sql    # App schema (sessions, messages, tool_calls, usage_events)
scripts/
└── setup_db.py        # One-shot DB setup (runs migrations + LangGraph checkpointer)
docs/
└── schema.md          # Full schema reference with ER diagram
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | required | Your OpenRouter API key |
| `OPENROUTER_MODEL` | `openai/gpt-4o` | Model to use (any OpenRouter model ID) |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter base URL |
| `AWS_REGION` | `us-east-1` | AWS region |
| `AWS_PROFILE` | none | AWS named profile (e.g. `devops-agent-readonly`) |
| `MAX_TOOL_CALLS` | `20` | Hard cap on tool calls per investigation |
| `INVESTIGATION_TIMEOUT` | `120` | Timeout in seconds |

## TODO / Roadmap

### Near-term
- [x] **Cache layer** — in-process TTL cache (`cachetools`) on all 19 AWS tool functions; 2-minute TTL, 256 entry max, AWS profile+region included in cache key
- [x] **Schema / models layer** — centralized `src/models/` package for all Pydantic models: agent domain, memory state, and API request/response schemas
- [ ] **Soft-deleted session cleanup job** — product version only; OSS users manage their own DB
- [ ] **Investigation history skill** — cross-session analysis: recurring errors, most-triggered alarms, patterns across all past sessions for a user
- [ ] **User roles** — `superadmin`, `admin`, `user`; role-based access to features and dashboards

### Medium-term
- [ ] **React frontend** — rewrite the single-file HTML UI in React; component-based architecture, proper state management, hot reload
- [ ] **Dashboard** — summarized view of troubleshooting activity, recurring incidents, query breakdown by service
- [ ] **Multi-provider LLM support** — plug in any OpenAI-compatible provider (Anthropic, OpenAI, LiteLLM, Ollama, local models) via a single config switch; provider-specific adapters where the API diverges
- [ ] **MCP integration** — expose the agent as an MCP server so it can be driven from Claude Desktop, Cursor, or any MCP-compatible client; UI panel to browse connected MCP tools
- [ ] **Custom tools via URL** — register external tools by pointing at an OpenAPI/HTTP endpoint; agent discovers and calls them alongside built-in AWS tools
- [ ] **Optimize tool loading** — pass only relevant tools per investigation context instead of the full 19-tool set
- [ ] **Message middleware pipeline** — compaction, summarization, intent detection, context trimmer
- [ ] **Guardrails** — input/output validation, PII scrubbing, query scope enforcement
- [ ] **Multi-model escalation** — route simple queries to cheaper/smaller models, escalate hard investigations to larger ones
- [x] **Fun streaming labels** — contextual loading copy ("Digging through CloudTrail…", "Lemonizing metrics…", "Cooking up a root cause…")

### Later
- [ ] **Observability** — OpenTelemetry traces for agent steps, tool call latency, LLM token usage
- [ ] **Session / user feedback loop** — thumbs up/down on investigations, feed signals back to the agent and to an internal quality dashboard
- [ ] **Slack integration** — post investigation results to a channel (`src/integrations/slack_webhook.py` stub ready)
- [ ] **Telegram integration** — bot that accepts `/investigate` commands and streams findings back to a chat or group
- [ ] **Knowledge base** — attach internal runbooks, post-mortems, and architecture docs so the agent grounds answers in org-specific context
- [ ] **Multi-account AWS** — support multiple AWS profiles per org via `aws_profiles` table (schema already in place)
- [ ] **Multi-cloud support** — extend tooling to GCP (Cloud Monitoring, Cloud Logging, GKE) and Azure (Monitor, Log Analytics, AKS); unified incident investigation across providers

### Product (SaaS)
- [ ] **Redis cache** — replace in-process `cachetools` with Redis; shared across workers, survives restarts, per-org cache namespacing to prevent data leakage between tenants
- [ ] **Soft-deleted session cleanup** — scheduled job (Inngest or APScheduler) to purge `is_deleted = TRUE` sessions older than a configurable retention window (default 30 days); GDPR right-to-erasure compliance
- [ ] **Auth & user roles** — `superadmin`, `admin`, `user`; JWT-based auth, role-based access control, org-scoped AWS credential management
- [ ] **Per-org AWS credential store** — encrypted credential vault per organization; agents use org-scoped profiles instead of a single global `AWS_PROFILE`
- [ ] **Billing & usage metering** — track token usage and tool calls per org/user; expose cost dashboards; integrate with Stripe for usage-based billing

## Development

```bash
# Run tests
uv run pytest

# Lint + format
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```
