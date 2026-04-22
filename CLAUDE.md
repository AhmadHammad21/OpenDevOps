# CLAUDE.md — OpenDevOps Agent

## Project Overview

Build **OpenDevOps Agent** — an open-source AWS DevOps Agent clone powered by OpenRouter LLMs.
It investigates incidents, analyzes root causes, and gives actionable mitigation plans — without
the AWS DevOps Agent price tag.

**Core principle:** Start simple, ship fast, iterate. Every phase must be independently useful.

---

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Language | **Python 3.11+** | boto3 is Python-first; rich DevOps tooling ecosystem |
| LLM Provider | **OpenRouter** (via OpenAI-compatible SDK) | Multi-model, cheap, swap-friendly |
| AWS SDK | **boto3** | Standard; read-only IAM role at start |
| CLI | **Typer** + **Rich** | Beautiful terminal UX |
| Config | **Pydantic Settings** + `.env` | Type-safe, easy to override |
| Packaging | **uv** (not pip) | Fast, modern Python package manager |
| Testing | **pytest** + **moto** (AWS mocking) | Mock AWS without real calls |

---

## Project Structure

```
opendevops-agent/
├── CLAUDE.md                   # This file
├── PLAN.md                     # Roadmap
├── README.md
├── pyproject.toml              # uv-managed dependencies
├── .env.example
│
└── src/
    ├── agent/
    │   ├── __init__.py
    │   ├── config.py               # Pydantic settings
    │   ├── core.py                 # Main agent loop (ReAct-style)
    │   ├── prompts.py              # All system + tool prompts
    │   ├── models.py               # Pydantic data models
    │   └── memory.py               # Investigation state / scratchpad
    │
    ├── tools/                      # AWS read-only tools (each = one file)
    │   ├── __init__.py
    │   ├── base.py                 # BaseTool class
    │   ├── cloudwatch.py           # Alarms, metrics, logs
    │   ├── cloudtrail.py           # API audit trail
    │   ├── ecs.py                  # ECS services, tasks, events
    │   ├── lambda_.py              # Lambda errors, throttles, config
    │   ├── ec2.py                  # Instance status, SGs, VPC
    │   ├── rds.py                  # DB events, performance insights
    │   └── iam.py                  # Role/policy read
    │
    ├── integrations/               # External signal sources
    │   ├── __init__.py
    │   └── slack_webhook.py        # Post findings to Slack (Phase 2)
    │
    └── cli/
        ├── __init__.py
        ├── main.py                 # `devops-agent` entrypoint (Typer)
        ├── investigate.py          # `investigate` command
        ├── ask.py                  # `ask` freeform Q&A command
        └── report.py               # `report` generate health summary

tests/
    ├── conftest.py
    ├── test_tools/
    └── test_agent/
```

---

## Environment Variables

```bash
# .env.example

# LLM
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet         # default, swappable
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# AWS (use IAM role or explicit keys)
AWS_REGION=us-east-1
AWS_PROFILE=devops-agent-readonly                    # optional

# Agent behavior
MAX_TOOL_CALLS=20           # hard cap per investigation
INVESTIGATION_TIMEOUT=120   # seconds
LOG_LEVEL=INFO
```

---

## Core Architecture: ReAct Agent Loop

The agent follows a **Reason → Act → Observe** loop:

```
User gives alarm/incident description
        ↓
[SYSTEM PROMPT + TOOLS SCHEMA]
        ↓
LLM reasons → picks a tool → calls it
        ↓
Tool returns observation
        ↓
LLM reasons again → more tools or final answer
        ↓
Final: Root Cause + Mitigation Plan (structured JSON)
```

**Tool calling:** Use OpenRouter's OpenAI-compatible `tools` parameter. Each AWS tool
is defined as a JSON schema function. The agent decides which to call.

**Max depth:** `MAX_TOOL_CALLS` prevents runaway loops.

---

## Phase 1 Implementation Checklist (MVP)

Claude Code should implement these in order. Mark each ✅ when done.

### Setup
- [ ] Init `pyproject.toml` with uv, add all dependencies
- [ ] Create `.env.example` and `pydantic_settings` config loader
- [ ] Write `README.md` with setup instructions

### Tools Layer (read-only AWS)
- [ ] `tools/base.py` — `BaseTool` abstract class with `name`, `description`, `schema`, `run()`
- [ ] `tools/cloudwatch.py`:
  - `get_alarms(state?)` — list alarms by state
  - `get_alarm_history(alarm_name, hours)` — alarm state changes
  - `get_metric_data(namespace, metric, dimensions, period, hours)` — raw metrics
  - `get_log_events(log_group, log_stream?, filter_pattern?, hours?)` — log tail
  - `describe_log_groups(prefix?)` — discover log groups
- [ ] `tools/cloudtrail.py`:
  - `lookup_events(hours, resource_name?, event_name?)` — recent API calls
- [ ] `tools/ecs.py`:
  - `list_services(cluster)` — services status
  - `describe_service(cluster, service)` — desired/running counts, events
  - `get_task_logs(cluster, task_id)` — fetch task stdout/stderr
- [ ] `tools/lambda_.py`:
  - `list_functions()` — all lambdas
  - `get_function_config(name)` — memory, timeout, env vars
  - `get_error_rate(name, hours)` — errors / throttles from CW
- [ ] `tools/ec2.py`:
  - `describe_instances(filters?)` — running instances, state
  - `get_system_status(instance_id)` — status checks
- [ ] `tools/rds.py`:
  - `describe_db_instances()` — DB status
  - `get_db_events(hours)` — RDS events log
- [ ] All tools: wrap boto3 calls in try/except, return structured dicts, never throw

### Agent Core
- [ ] `agent/models.py` — define:
  - `Investigation` (input: description, alarm_name?, service?)
  - `Finding` (hypothesis, evidence, confidence)
  - `InvestigationResult` (root_cause, mitigation_steps, confidence, services_affected)
- [ ] `agent/prompts.py` — write the system prompt (see Prompt Guidelines below)
- [ ] `agent/core.py` — implement `InvestigationAgent`:
  - `investigate(description) -> InvestigationResult`
  - ReAct loop with tool calling
  - Structured JSON output on final answer
  - Logging every tool call + result for transparency

### CLI
- [ ] `cli/main.py` — Typer app with `--help`
- [ ] `cli/investigate.py` — `devops-agent investigate "describe the problem"`
  - Accept `--alarm`, `--service`, `--region` flags
  - Show live spinner during investigation (Rich)
  - Print final report as a beautiful Rich panel
- [ ] `cli/ask.py` — `devops-agent ask "why is my Lambda throttling?"`
  - One-shot Q&A with AWS context
- [ ] `cli/report.py` — `devops-agent report` 
  - Generate a daily ops health summary (alarm counts, recent errors)

### Tests
- [ ] Mock all AWS calls with `moto`
- [ ] Test each tool in isolation
- [ ] Test agent loop with a fake alarm scenario

---

## Prompt Guidelines

The system prompt in `agent/prompts.py` must:

1. **Define the role:** "You are an expert AWS SRE investigating an incident. You have read-only access to AWS services via tools."

2. **Investigation methodology:** Tell the agent to:
   - Start by checking CloudWatch alarms for the affected service
   - Check CloudTrail for recent changes (deployments, config changes) in the last 2 hours
   - Correlate metric spikes with log errors
   - Form hypotheses explicitly before calling tools to verify them
   - Rank hypotheses by likelihood

3. **Root cause categories** (tell the agent to classify into):
   - `SYSTEM_CHANGE` — recent deployment or config change caused it
   - `INPUT_ANOMALY` — traffic spike, bad payloads
   - `RESOURCE_LIMIT` — throttling, OOM, disk full
   - `COMPONENT_FAILURE` — unhealthy instance, crashed pod
   - `DEPENDENCY_ISSUE` — downstream service, DB, third-party API

4. **Output format:** Always end with a structured JSON block:
   ```json
   {
     "root_cause_category": "SYSTEM_CHANGE",
     "root_cause_summary": "...",
     "evidence": ["..."],
     "mitigation_steps": ["1. ...", "2. ..."],
     "validation_steps": ["..."],
     "confidence": "HIGH|MEDIUM|LOW",
     "services_affected": ["..."],
     "recommended_follow_up": "..."
   }
   ```

5. **Tone:** Be concise. Skip obvious observations. Go straight to anomalies.

---

## IAM Policy (Read-Only Role)

The agent needs this IAM policy attached to its role/user:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "OpenDevOpsAgentReadOnly",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:Describe*",
        "cloudwatch:Get*",
        "cloudwatch:List*",
        "logs:Describe*",
        "logs:Get*",
        "logs:Filter*",
        "logs:StartQuery",
        "logs:GetQueryResults",
        "cloudtrail:LookupEvents",
        "cloudtrail:GetTrailStatus",
        "ecs:Describe*",
        "ecs:List*",
        "ec2:Describe*",
        "lambda:List*",
        "lambda:Get*",
        "rds:Describe*",
        "iam:Get*",
        "iam:List*",
        "sts:GetCallerIdentity",
        "ce:GetCostAndUsage",
        "ce:GetAnomalies"
      ],
      "Resource": "*"
    }
  ]
}
```

Create this as `iam-policy.json` in the repo root.

---

## Code Style Rules

- Use **type hints everywhere** — no untyped functions
- Use **Pydantic models** for all data in/out of tools
- All tool functions must be **synchronous** (boto3 is sync; keep it simple)
- **Never** store credentials in code — use env vars or AWS profiles
- Each tool file must have a module docstring explaining what AWS service it covers
- Keep tool functions **small and single-purpose** — one API call per function
- Use `logging` (not print) with `structlog` for structured output
- Format with **ruff** (linting + formatting in one)

---

## Dependencies (pyproject.toml)

```toml
[project]
name = "opendevops-agent"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "openai>=1.30.0",          # OpenRouter is OpenAI-compatible
    "boto3>=1.34.0",
    "typer>=0.12.0",
    "rich>=13.7.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.3.0",
    "python-dotenv>=1.0.0",
    "structlog>=24.1.0",
]

[tool.uv.dev-dependencies]
dev = [
    "pytest>=8.0.0",
    "moto[cloudwatch,logs,ec2,ecs,lambda,rds,iam,cloudtrail]>=5.0.0",
    "pytest-mock>=3.14.0",
    "ruff>=0.4.0",
]
```

---

## Git Workflow

- Branch: `main` (stable) + `dev` (active work)
- Commit format: `feat:`, `fix:`, `docs:`, `test:`
- Write a `CHANGELOG.md` entry for each phase completion

---

## What NOT to build in Phase 1

- ❌ No web UI (CLI only)
- ❌ No write/remediation actions (read-only is safer and simpler)
- ❌ No Slack integration yet
- ❌ No persistent database
- ❌ No multi-account AWS support yet
- ❌ No custom skill system yet

All of these are Phase 2+. Keep the scope tight.
