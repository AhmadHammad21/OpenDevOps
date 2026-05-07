# CLAUDE.md — OpenDevOps Agent

## Project Overview

**OpenDevOps Agent** — an open-source AWS incident investigation agent powered by any LLM via LiteLLM/OpenRouter. It investigates alarms, analyzes root causes, and produces structured mitigation plans.

**Core principle:** Every feature must be independently useful. Read-only AWS access only.

---

## Current State

Everything below is **already built and working:**

- **Agent framework:** DeepAgents (thin wrapper over LangGraph ReAct loop) with LiteLLM for multi-provider LLM support (OpenRouter, Anthropic, OpenAI, Ollama, custom endpoints)
- **21 read-only AWS tools** across CloudWatch (6), CloudTrail (2), ECS (4), Lambda (4), EC2 (2), RDS (2), IAM (1), plus bash escape hatch, history cross-session analytics, skills system, and `submit_investigation` final answer tool
- **3 storage backends:** memory (default, CI-safe), SQLite (local persistence), PostgreSQL (production)
- **Streaming FastAPI backend:** SSE real-time token streaming + tool call events
- **React/TypeScript/Vite frontend:** Chat page (streaming), session sidebar, history search, dashboard analytics, settings page
- **CLI:** `investigate`, `ask`, `report`, `ui`, `mcp` commands via Typer
- **MCP server:** Exposes `investigate`, `ask`, `list_sessions` to Claude Desktop, Cursor, etc.
- **Tool response capping:** `with_cap()` wrapper truncates responses > `TOOL_RESPONSE_MAX_CHARS` (default 40K chars) before passing to LLM
- **In-process caching:** `@tool_cached` — 2-min TTL, 256-entry LRU, keyed on function + AWS profile + region + args
- **Conversation summarization:** Auto-compacts long sessions when total chars > threshold; tracked in `usage_events.metadata` and shown on dashboard
- **Skills system:** Markdown runbooks in `src/skills/*/SKILL.md`; agent calls `list_skills()` / `use_skill(name)` at runtime
- **Slack integration:** Reactive notifications after investigations + proactive polling loop for CloudWatch/Lambda anomalies
- **Dashboard:** Session counts, tool call stats, cost/latency, context saved, activity chart, service breakdown, root cause distribution, recent sessions

---

## Current Priorities

From `README.md` TODO:

1. **Custom tools via URL** — let users plug in extra tools without touching source
2. **Bash sandbox Phase 2** — throwaway Docker container instead of subprocess allowlist
3. **Optimize tool loading** — pass only relevant tools per context (reduce prompt size)
4. **Observability** — OpenTelemetry traces
5. **Follow-up question suggestions** — auto-generate 3 drill-down questions after each investigation
6. **Knowledge base** — attach runbooks, post-mortems, architecture docs beyond the skills system
7. **Multi-account AWS support**
8. **Auth & user roles** (product/SaaS path)

---

## What NOT to Change Without Discussion

- **Agent framework:** `deepagents` + `langgraph` — the ReAct loop, checkpointing, and tool dispatch all depend on this. Do not swap for a different framework.
- **SSE streaming contract:** The event types (`content`, `tool_call_started`, `tool_call_completed`, `tool_call_error`, `done`) are consumed by the frontend. Changing names or payload shapes breaks the UI.
- **LangGraph checkpointer integration:** The checkpointer is passed into `create_deep_agent()` and is what makes session continuity work. Don't bypass it or write messages to the DB outside of the normal `save_*` calls.
- **Tool function signatures:** Tool functions are plain Python functions — DeepAgents infers the JSON schema from their signatures and docstrings. Adding `*args`, `**kwargs`, or removing type hints will break schema inference.
- **Database schema:** Tables `sessions`, `messages`, `tool_calls`, `usage_events` have a defined shape. New columns need a migration in `migrations/`. Don't add columns inline.
- **`docs/` folder:** All `.md` files in `docs/` are the source for the public documentation site. Keep them accurate when changing features.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Agent framework | DeepAgents + LangGraph |
| LLM abstraction | LiteLLM (100+ providers; default OpenRouter) |
| AWS SDK | boto3 (read-only) |
| Web backend | FastAPI + Uvicorn (SSE streaming) |
| CLI | Typer + Rich |
| Config | Pydantic Settings + `.env` |
| Storage | memory / aiosqlite / psycopg async |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| Caching | cachetools (in-process TTL cache) |
| Testing | pytest + moto |
| Package manager | **uv — always use `uv run` and `uv add`, never bare `pip`** |
| Logging | Loguru |

---

## Project Structure

```
src/
├── agent/
│   ├── core.py             # Agent init (create_deep_agent) + invocation
│   ├── prompts.py          # System prompt — investigation methodology
│   ├── summarizer.py       # Conversation compaction (auto-summarize long sessions)
│   ├── turns.py            # Turn persistence, cost calc, Slack notify
│   ├── poller.py           # Background anomaly detection loop
│   └── db/
│       ├── base.py         # DatabaseBackend ABC
│       ├── memory.py       # In-memory (MemorySaver)
│       ├── sqlite.py       # SQLite (aiosqlite + LangGraph checkpointer)
│       └── postgres.py     # PostgreSQL (psycopg async + AsyncPostgresSaver)
├── api/
│   ├── app.py              # FastAPI factory, lifespan, static files
│   ├── sessions.py         # Session state helpers
│   ├── streaming_labels.py # Contextual loading copy for SSE status events
│   └── routers/
│       ├── chat.py         # POST /chat → SSE stream
│       ├── sessions.py     # GET/DELETE /sessions
│       ├── history.py      # GET /history/* (cross-session analytics)
│       └── dashboard.py    # GET /stats
├── cli/
│   ├── main.py             # Typer entrypoint
│   ├── investigate.py      # investigate command
│   ├── ask.py              # ask command
│   ├── report.py           # report command
│   ├── ui.py               # ui command (start web server)
│   └── mcp.py              # mcp command (start MCP server)
├── tools/
│   ├── cloudwatch.py       # 6 tools: alarms, metrics, logs, insights, log groups, alarm history
│   ├── cloudtrail.py       # 2 tools: trail events, event lookup
│   ├── ecs.py              # 4 tools: clusters, services, service detail, tasks
│   ├── lambda_.py          # 4 tools: list, config, error rate, concurrent execs
│   ├── ec2.py              # 2 tools: list instances, instance details
│   ├── rds.py              # 2 tools: list DBs, DB details
│   ├── iam.py              # 1 tool: describe role + policies
│   ├── bash_tool.py        # run_bash_command (allowlisted read-only AWS CLI/kubectl/docker)
│   ├── history.py          # get_investigation_history, search_past_investigations
│   ├── skills.py           # list_skills, use_skill
│   ├── final_answer.py     # submit_investigation (structured output)
│   ├── _cache.py           # @tool_cached decorator
│   └── _cap.py             # with_cap() response truncation wrapper
├── config/
│   └── appsettings.py      # Pydantic Settings (single source of truth)
├── models/
│   ├── agent.py            # Investigation, InvestigationResult, RootCauseCategory, Confidence
│   ├── chat.py             # ChatRequest
│   └── sessions.py         # SessionSummary, MessageRecord, ToolCallRecord, UsageRecord
├── integrations/
│   └── slack_webhook.py    # Block Kit notification sender
├── skills/
│   └── lambda-throttling/SKILL.md   # Runbook: Lambda throttling investigation
└── mcp_server.py           # MCP HTTP+SSE server (fastmcp)

frontend/src/
├── pages/
│   ├── ChatPage.tsx        # Streaming chat, tool call inspector, cost card
│   ├── DashboardPage.tsx   # Analytics dashboard
│   ├── HistoryPage.tsx     # Cross-session search
│   └── SettingsPage.tsx    # Read-only config view
└── components/             # AgentMessage, InputArea, Sidebar, ToolCallsBox, UsageBox, ...

migrations/
├── 001_initial.sql         # All tables + indexes
├── 002_soft_delete.sql     # is_deleted, deleted_at columns on sessions
└── 003_usage_events_metadata.sql   # JSONB metadata column on usage_events

docs/                       # Public documentation source (one .md per feature)
```

---

## Environment Variables

```bash
# LLM
LLM_MODEL=openrouter/anthropic/claude-3.5-sonnet   # LiteLLM format
LLM_API_KEY=sk-or-...
LLM_API_BASE=https://openrouter.ai/api/v1           # omit for direct Anthropic/OpenAI

# AWS
AWS_REGION=us-east-1
AWS_PROFILE=devops-agent-readonly                   # optional

# Storage backend
CHECKPOINT_BACKEND=memory                           # memory | sqlite | postgres
SQLITE_PATH=./data/agent.db
DATABASE_URL=postgresql://user:pass@host/db         # postgres only

# Agent behavior
MAX_TOOL_CALLS=20
INVESTIGATION_TIMEOUT=120
TOOL_RESPONSE_MAX_CHARS=40000

# Conversation summarization
SUMMARIZATION_ENABLED=true
SUMMARIZATION_THRESHOLD_CHARS=60000
SUMMARIZATION_KEEP_CHARS=20000

# Slack + proactive polling
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
POLL_INTERVAL_MINUTES=0                             # 0 = disabled
POLL_ERROR_THRESHOLD=5.0                            # Lambda error % to trigger investigation
POLL_REINVESTIGATE_HOURS=1
```

---

## Core Architecture

```
User message (CLI or /chat POST)
  → maybe_summarize() if session is long
  → agent.ainvoke(messages, thread_id=session_id)
      LangGraph ReAct loop:
        LLM reasons → picks tool → invoke tool
          @tool_cached (TTL cache check)
          with_cap() (truncate if > TOOL_RESPONSE_MAX_CHARS)
          boto3 / subprocess call
          return result to LLM
        repeat until submit_investigation() or MAX_TOOL_CALLS
  → stream tokens + tool events via SSE
  → save turn (session, messages, tool_calls, usage_event) to DB backend
  → maybe notify Slack
```

The checkpointer (memory / SQLite / Postgres) stores full LangGraph thread state. Each `/chat` call resumes the thread by `thread_id = session_id`, so the agent sees full history without the API passing it explicitly.

---

## Code Style Rules

- Type hints everywhere — no untyped functions
- Pydantic models for structured data in/out
- Tool functions are **synchronous** (boto3 is sync) — async lives in the API layer
- Credentials only via env vars or AWS profiles — never hardcoded
- Tool functions: small and single-purpose, one boto3 call each, always return a dict, never raise
- Use `logger` (Loguru) not `print`
- Format/lint with **ruff**
- `uv run`, `uv add` — never bare `pip`

---

## Git Workflow

- `main` — stable, merged via PR
- Feature branches: `feat/<name>`, `fix/<name>`, `docs/<name>`
- Commit format: `feat:`, `fix:`, `docs:`, `test:`, `ci:`
- Do not commit `.env` files or AWS credentials
