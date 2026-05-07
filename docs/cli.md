# CLI Reference

The `devops-agent` CLI is powered by Typer and Rich. All commands share the same
LLM and AWS configuration from `.env`.

```bash
uv run devops-agent --help
```

---

## `investigate`

Investigate an AWS incident and produce a structured root cause report.

```bash
uv run devops-agent investigate "<description>" [OPTIONS]
```

| Option | Short | Description |
|---|---|---|
| `--alarm` | `-a` | CloudWatch alarm name to investigate |
| `--service` | `-s` | Service name (e.g. ECS service name) |
| `--region` | `-r` | AWS region override |
| `--json` | | Output raw JSON instead of the Rich panel |

**Examples:**

```bash
# Basic incident description
uv run devops-agent investigate "high error rate on my payment Lambda"

# With alarm and service hints
uv run devops-agent investigate "latency spike" --alarm HighLatencyAlarm --service api-service

# Machine-readable output
uv run devops-agent investigate "ECS tasks keep crashing" --json
```

**Output (Rich panel):**
- Root cause category and summary
- Confidence level (HIGH / MEDIUM / LOW)
- Evidence list
- Mitigation steps
- Validation steps
- Services affected
- Recommended follow-up

**JSON output fields:** `root_cause_category`, `root_cause_summary`, `evidence`,
`mitigation_steps`, `validation_steps`, `confidence`, `services_affected`,
`recommended_follow_up`, `tool_calls_made`.

---

## `ask`

Ask a freeform question about your AWS environment. No tool calls — direct LLM answer.

```bash
uv run devops-agent ask "<question>"
```

**Examples:**

```bash
uv run devops-agent ask "why would a Lambda function suddenly start throttling?"
uv run devops-agent ask "what CloudWatch metrics should I watch for RDS failovers?"
```

Output is rendered as Markdown in the terminal via Rich.

---

## `report`

Generate a daily ops health summary showing CloudWatch alarm states.

```bash
uv run devops-agent report [OPTIONS]
```

| Option | Short | Description |
|---|---|---|
| `--region` | `-r` | AWS region override |

**Output:**
- Summary table: OK / ALARM / INSUFFICIENT_DATA counts
- Table of currently firing alarms with metric name and state reason

```bash
uv run devops-agent report
```

---

## `ui`

Launch the web UI chat interface locally.

```bash
uv run devops-agent ui [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | Bind host |
| `--port` / `-p` | `8000` | Port to listen on |

```bash
# Default
uv run devops-agent ui

# Expose to LAN
uv run devops-agent ui --host 0.0.0.0 --port 8080
```

Opens the full React UI + FastAPI backend in one process. The frontend is served
as static files from the same process — no separate Vite server needed.

---

## `mcp`

Start the agent as an MCP (Model Context Protocol) server, exposing `investigate`,
`ask`, and `list_sessions` tools to MCP-compatible clients like Claude Desktop or Cursor.

```bash
uv run devops-agent mcp [OPTIONS]
```

See [`mcp_server.md`](mcp_server.md) for full setup instructions and transport options.

---

## Global behaviour

- **Logging** — level controlled by `LOG_LEVEL` in `.env` (default `INFO`); logs go to stderr
- **Timeout** — all LLM calls respect `INVESTIGATION_TIMEOUT` (default 120s)
- **AWS profile** — all commands use `AWS_PROFILE` from `.env` if set
- **Model** — all commands use `LLM_MODEL` from `.env`
