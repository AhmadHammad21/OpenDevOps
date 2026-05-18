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

Go to **Settings → AWS Configuration** after first login. Enter your AWS Region and optional SNS Topic ARN, save, then click **Run checks** to verify IAM permissions. Click **Create Infrastructure** to create the SQS queue, EventBridge rules, and aggregate Lambda CloudWatch alarm.

### Option B — Manual `.env`

```bash
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/opendevops-events
EVENT_CONSUMER_ENABLED=true        # or leave unset — consumer also starts if SQS_QUEUE_URL is set
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:123456789012:opendevops-alerts
```

The consumer starts automatically on server startup if either `EVENT_CONSUMER_ENABLED=true`, `SQS_QUEUE_URL` is set, or the init wizard has enabled event infrastructure in persistent app config.

---

## EventBridge Rules

`setup_event_infra()` (`src/agent/event_infra.py`) creates one SQS queue and nine EventBridge rules, all prefixed `opendevops-`:

| Rule | Events captured |
|---|---|
| `opendevops-alarm-state` | CloudWatch Alarm state changes to `ALARM` |
| `opendevops-lambda-failure` | Lambda async invocation failures |
| `opendevops-lambda-throttle` | Lambda throttling errors |
| `opendevops-ecs-task-stopped` | ECS task stopped with non-zero exit / OOM |
| `opendevops-ec2-state` | EC2 instance state changes |
| `opendevops-rds-events` | RDS instance failures and failovers |
| `opendevops-health` | AWS Health personal health events |
| `opendevops-codedeploy-failure` | CodeDeploy deployment failures |
| `opendevops-guardduty` | GuardDuty findings |

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

1. Receives up to 5 messages per poll with a 20-second long-poll wait
2. Filters noise: only processes events where `_is_real_failure()` returns true (e.g. skips EC2 `running` state changes, healthy RDS events)
3. Deduplicates: checks an in-memory set (`_in_progress`) and the database to skip events already being investigated or investigated within the last 3 minutes
4. Calls `collect_context(event)` to enrich the prompt
5. Generates a `session_id` and runs a full agent investigation via `agent.ainvoke`, persisting the session and messages to the database (`source = 'event'`)
6. Persists the result to the `alerts` table (linked to the session via `session_id`) via `monitor_store.add_alert()`
7. Delivers findings via SNS and Slack (if configured); failed investigations are flagged with status `'failed'` but are still persisted and notified
8. Deletes the SQS message

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
sqs:ReceiveMessage, sqs:DeleteMessage, sqs:DeleteQueue, sqs:ListQueues
events:PutRule, events:PutTargets, events:ListRules
events:RemoveTargets, events:DeleteRule
cloudwatch:PutMetricAlarm, cloudwatch:DeleteAlarms, cloudwatch:DescribeAlarms
```

Use **Settings → AWS Configuration → Run checks** to validate all permissions before going live.

---

## Persistence

Each event-driven investigation creates a full session (messages, tool calls, usage events) in the database, linked to the alert via `session_id`. This powers the "View investigation" button on the Monitoring page, which opens the original chat instead of starting a fresh one.

Sessions created by the event consumer carry `source = 'event'` and are hidden from the sidebar by default. They become visible after the user sends a follow-up message in the chat (`user_interacted` is then set to `true`).

The `alerts` table records `status` (`'completed'` or `'failed'`), `dedup_key` (MD5 fingerprint of stable event fields for cross-run deduplication), and `session_id` (FK to the session that produced it).

All three storage backends (memory, SQLite, PostgreSQL) support alerts. For PostgreSQL, run migrations before starting the server:

```bash
uv run python scripts/setup_db.py
```

For SQLite, schema migrations are applied automatically on first start.

---

## Source Files

| File | Purpose |
|---|---|
| `src/agent/event_consumer.py` | SQS long-poll loop, filtering, prompt building, delivery |
| `src/agent/event_infra.py` | Create/teardown SQS queue + EventBridge rules |
| `src/agent/context_collectors.py` | Per-event-type boto3 context enrichment |
| `src/agent/monitor_store.py` | In-memory service status + DB-backed alert persistence |
| `src/agent/init_store.py` | Persist init config to DB-backed `app_config` with `data/init.json` fallback/cache |
| `src/agent/permission_checker.py` | IAM permission validation |
| `src/tools/sns.py` | SNS publish wrapper |
| `src/api/routers/init.py` | Setup wizard API endpoints |
| `migrations/005_alerts.sql` | PostgreSQL alerts table + indexes |
