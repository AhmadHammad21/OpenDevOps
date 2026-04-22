# OpenDevOps Agent

Open-source AWS DevOps Agent powered by OpenRouter LLMs. Investigates incidents, finds root causes,
and gives actionable mitigation plans — without the AWS DevOps Agent price tag.

## What's inside

- **LangChain DeepAgents** as the agent framework — planning, tool orchestration, and session memory out of the box
- **18 read-only AWS tools** across CloudWatch, CloudTrail, ECS, Lambda, EC2, RDS, and IAM — plain Python functions, schemas inferred automatically
- **Web UI** — FastAPI backend with a chat interface that shows live tool calls (name, args, result) as they happen
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

### 4. Run

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
├── agent/         # DeepAgents setup, prompts, models, config
├── tools/         # 18 read-only AWS tool functions
├── api/           # FastAPI + SSE streaming endpoint
├── cli/           # Typer CLI commands
└── integrations/  # Future: Slack, PagerDuty
frontend/
└── index.html     # Chat UI with live tool call inspector
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

## Development

```bash
# Run tests
uv run pytest

# Lint + format
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```
