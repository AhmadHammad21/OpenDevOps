# Event-Driven Incident Detection

OpenDevOps Agent supports two complementary detection modes that run simultaneously:

| Mode | Source | Trigger |
|---|---|---|
| **Proactive polling** | CloudWatch Alarms + Lambda metrics | Checked every N minutes by a background loop |
| **Event-driven consumer** | EventBridge → SQS | Real AWS infrastructure events delivered in near-real time |

This page covers the event-driven consumer. For the polling loop see [slack_and_polling.md](slack_and_polling.md).

---

## Architecture

```
AWS Service (ECS, Lambda, RDS, EC2…)
  → CloudWatch → EventBridge rule
      → SQS queue (OpenDevOps)
          → SQS long-poll consumer (event_consumer_loop)
              → context_collectors (deterministic boto3 enrichment)
              → agent.ainvoke (LLM investigation)
              → monitor_store.add_alert (persist result)
              → SNS publish + Slack notify
```

---

## Setup

### Option A — Init wizard (recommended)

Go to **Settings → AWS Configuration** after first login. Enter your SNS Topic ARN and AWS Region, save, then click **Run checks** to verify IAM permissions. The SQS queue and EventBridge rules are created automatically the first time the server starts with valid config.

### Option B — Manual `.env`

```bash
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/opendevops-events
EVENT_CONSUMER_ENABLED=true        # or leave unset — consumer also starts if SQS_QUEUE_URL is set
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:123456789012:opendevops-alerts
```

The consumer starts automatically on server startup if either `EVENT_CONSUMER_ENABLED=true` or `SQS_QUEUE_URL` is set.

---

## EventBridge Rules

`setup_event_infra()` (`src/agent/event_infra.py`) creates one SQS queue and nine EventBridge rules, all prefixed `opendevops-`:

| Rule | Events captured |
|---|---|
| `opendevops-cloudwatch-alarms` | CloudWatch Alarm state changes |
| `opendevops-ecs-failures` | ECS task stopped with non-zero exit / OOM |
| `opendevops-lambda-errors` | Lambda async invocation failures |
| `opendevops-rds-events` | RDS instance failures and failovers |
| `opendevops-ec2-state` | EC2 instance state changes |
| `opendevops-asg-events` | Auto Scaling launch / terminate failures |
| `opendevops-codepipeline` | CodePipeline stage failures |
| `opendevops-ssm-compliance` | SSM patch compliance failures |
| `opendevops-health-events` | AWS Health personal health events |

---

## Context Collectors

Before the LLM runs, `collect_context(event)` in `src/agent/context_collectors.py` makes deterministic boto3 calls to gather facts about the affected resource. This reduces LLM tool calls by front-loading the most relevant data.

| Event type | Context fetched |
|---|---|
| CloudWatch Alarm | Alarm details, metric statistics (1 h), recent log errors |
| ECS task failure | Cluster/service description, stopped reason, recent task logs |
| Lambda failure | Function config, recent error rate + invocations (1 h) |
| RDS event | DB instance details |
| EC2 state change | Instance description |

Context is appended to the investigation prompt, capped at 3 000 chars to stay within token budgets.

---

## SQS Long-Poll Consumer

`event_consumer_loop()` in `src/agent/event_consumer.py`:

1. Receives up to 10 messages per poll with a 20-second long-poll wait
2. Filters noise: only processes events where `_is_real_failure()` returns true (e.g. skips EC2 `running` state changes, healthy RDS events)
3. Calls `collect_context(event)` to enrich the prompt
4. Runs a full agent investigation via `agent.ainvoke`
5. Persists the result to the `alerts` table via `monitor_store.add_alert()`
6. Delivers findings via SNS and Slack (if configured)
7. Deletes the SQS message

The consumer is started as an `asyncio.Task` in the FastAPI lifespan and shut down cleanly on server stop.

---

## SNS Alert Delivery

After each event-driven investigation, the result is published to the configured SNS topic (`SNS_TOPIC_ARN`). The message is a JSON payload:

```json
{
  "service": "ECS / my-api",
  "confidence": "HIGH",
  "error": "Container exited with code 137 (OOM killed)",
  "resolution": "Increase task memory from 512 MB to 1024 MB..."
}
```

SNS subscribers (email, Lambda, SQS fan-out, etc.) receive this payload. Configure subscribers in your AWS console.

Slack notifications fire alongside SNS when `SLACK_WEBHOOK_URL` is set — both channels always receive the same result.

---

## Permission Requirements

The IAM role/user used by the agent needs these additional permissions for event-driven detection:

```
sns:Publish, sns:GetTopicAttributes
sqs:CreateQueue, sqs:SetQueueAttributes, sqs:GetQueueAttributes
sqs:ReceiveMessage, sqs:DeleteMessage, sqs:ListQueues
events:PutRule, events:PutTargets, events:ListRules
events:RemoveTargets, events:DeleteRule
```

Use **Settings → AWS Configuration → Run checks** to validate all permissions before going live.

---

## Persistence

Completed investigations are stored in the `alerts` table across all three storage backends (memory, SQLite, PostgreSQL). The Monitoring dashboard reads from this table.

For PostgreSQL, run the migration before starting the server:

```bash
uv run python scripts/setup_db.py
```

For SQLite, the `alerts` table is created automatically on first start.

---

## Source Files

| File | Purpose |
|---|---|
| `src/agent/event_consumer.py` | SQS long-poll loop, filtering, prompt building, delivery |
| `src/agent/event_infra.py` | Create/teardown SQS queue + EventBridge rules |
| `src/agent/context_collectors.py` | Per-event-type boto3 context enrichment |
| `src/agent/monitor_store.py` | In-memory service status + DB-backed alert persistence |
| `src/agent/init_store.py` | Persist init config to `data/init.json` |
| `src/agent/permission_checker.py` | IAM permission validation |
| `src/tools/sns.py` | SNS publish wrapper |
| `src/api/routers/init.py` | Setup wizard API endpoints |
| `migrations/005_alerts.sql` | PostgreSQL alerts table + indexes |
