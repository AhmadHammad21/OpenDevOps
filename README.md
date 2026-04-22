# OpenDevOps Agent

Open-source AWS DevOps Agent powered by OpenRouter LLMs. Investigates incidents, finds root causes,
and gives actionable mitigation plans — without the AWS DevOps Agent price tag.

## Quick Start

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — add your OPENROUTER_API_KEY and AWS credentials
```

### 3. Run

```bash
# Investigate an incident
devops-agent investigate "high error rate on my payment Lambda"

# With specific alarm and service
devops-agent investigate "latency spike" --alarm HighLatencyAlarm --service api-service

# Freeform Q&A
devops-agent ask "why would a Lambda function suddenly start throttling?"

# Daily ops health report
devops-agent report
```

## AWS Profile Setup

Create a local AWS profile using your access key and secret:

```bash
aws configure --profile devops-agent-readonly
# AWS Access Key ID:     your_key_id
# AWS Secret Access Key: your_secret_key
# Default region:        us-east-1
# Default output format: json
```

Verify it works:

```bash
aws sts get-caller-identity --profile devops-agent-readonly
```

## AWS IAM Setup

Attach `iam-policy.json` to the IAM user or role your agent uses. It grants read-only access
to CloudWatch, CloudTrail, ECS, Lambda, EC2, RDS, and IAM.

```bash
aws iam create-policy \
  --policy-name OpenDevOpsAgentReadOnly \
  --policy-document file://iam-policy.json
```

## Development

```bash
# Run tests (no real AWS calls needed)
uv run pytest

# Lint + format
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

## Project Structure

```
src/
├── agent/      # ReAct agent loop, models, prompts
├── tools/      # AWS read-only tools (CloudWatch, CloudTrail, ECS, Lambda, EC2, RDS, IAM)
├── cli/        # Typer CLI commands
└── integrations/  # Future: Slack, PagerDuty
tests/          # moto-mocked unit tests
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | required | Your OpenRouter API key |
| `OPENROUTER_MODEL` | `openai/gpt-4o` | Model to use (any OpenRouter model ID) |
| `AWS_REGION` | `us-east-1` | AWS region |
| `AWS_PROFILE` | none | AWS profile name |
| `MAX_TOOL_CALLS` | `20` | Hard cap on tool calls per investigation |
| `INVESTIGATION_TIMEOUT` | `120` | Timeout in seconds |
