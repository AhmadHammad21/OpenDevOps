# Event-Driven Incident Detection

OpenDevOps Agent supports two complementary detection modes that run simultaneously:

| Mode | Source | Trigger |
|---|---|---|
| **Proactive polling** | CloudWatch Alarms + Lambda metrics | Checked every N seconds by a background loop |
| **Event-driven consumer** | EventBridge → SQS | Real AWS infrastructure events delivered in near-real time |

This page covers the event-driven consumer. For the polling loop see [slack_and_polling.md](slack_and_polling.md).

---

## Architecture

```
AWS Service (ECS, Lambda, RDS, EC2…)
  → CloudWatch → EventBridge rule
      → SQS queue (OpenDevOps, with DLQ)
          → SQS long-poll consumer (event_consumer_loop)
              → context_collectors (deterministic boto3 enrichment)
              → investigation_runner.run_investigation (LLM investigation)
              → monitor_store.add_alert (persist result + SSE push)
              → Slack / Telegram notify
```

---

## Setup

### Option A — Init wizard (recommended)

Go to **Settings → AWS Configuration** after first login. Enter your AWS Region, save, then click **Run checks** to verify IAM permissions. Click **Create Infrastructure** to create the SQS queue, EventBridge rules, and aggregate Lambda CloudWatch alarm.

### Option B — Manual `.env`

```bash
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/opendevops-agent-events
EVENT_CONSUMER_ENABLED=true        # or leave unset — consumer also starts if SQS_QUEUE_URL is set
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
3. Deduplicates: builds a canonical incident key and atomically claims it in the database before the agent runs
4. Calls `collect_context(event)` to enrich the prompt
5. Generates a `session_id` and runs a full agent investigation via `investigation_runner.run_investigation`, persisting the session and messages to the database (`source = 'event'`)
6. Persists the result to the `alerts` table (linked to the session via `session_id`) via `monitor_store.add_alert()`, which also pushes the alert to all active SSE subscribers
7. Delivers findings via Slack and Telegram (if configured); failed investigations are flagged with status `'failed'` but are still persisted and notified. If the LLM completes the loop without calling `submit_investigation` (e.g. a weak model), a synthetic `_status: failed` result is produced so the alert is always persisted.
8. Deletes the SQS message only after successful processing, an intentional ignore, or a duplicate claim. Processing failures are left on the queue for retry and eventual DLQ redrive.

The consumer is started as an `asyncio.Task` in the FastAPI lifespan and shut down cleanly on server stop.

The setup wizard creates both `opendevops-agent-events` and `opendevops-agent-events-dlq`. The main queue has a redrive policy with `maxReceiveCount=5`; poison messages remain available in the DLQ for inspection instead of being dropped by the consumer.

Deduplication uses canonical incident keys rather than hashes of whole event payloads. Examples: `cloudwatch_alarm:us-east-1:high-error-rate`, `lambda_errors:us-east-1:payment-processor`, and `lambda_error:us-east-1:payment-processor:<signature>`. Lambda EventBridge failures with different error signatures are separate incidents. Metric polling only sees function-level error rates, so those incidents are deduped at the function level during the cooldown window.

---

## Permission Requirements

The IAM role/user needs the permissions described in [iam_setup.md](iam_setup.md). For event-driven detection specifically:

- **Policy 1 (Operational)** — `SQSConsume` statement provides `ReceiveMessage`, `DeleteMessage`, `ChangeMessageVisibility` on `opendevops-agent-events`
- **Policy 2 (Setup)** — `SQSSetup`, `EventBridgeSetup`, and `CloudWatchAlarmSetup` statements with write actions scoped to `opendevops-*` resources

Use **Settings → AWS Configuration → Run checks** to validate all permissions before going live.

---

## Persistence

Each event-driven investigation creates a full session (messages, tool calls, usage events) in the database, linked to the alert via `session_id`. This powers the "View investigation" button on the Monitoring page, which opens the original chat instead of starting a fresh one.

Sessions created by the event consumer carry `source = 'event'` and are hidden from the sidebar by default. They become visible after the user sends a follow-up message in the chat (`user_interacted` is then set to `true`).

The `alerts` table records `status` (`'completed'` or `'failed'`), `dedup_key` (the canonical incident key), `session_id` (FK to the session that produced it), and `trigger_source` (`'poller'` or `'event_consumer'`). The `incident_claims` table stores the atomic pre-investigation claim used to prevent duplicate agent runs across workers and restarts.

Autonomous polling and event-driven monitoring require SQLite or PostgreSQL because incident claims must be durable. The memory backend remains available for chat, CI, and quick demos, but the poller, event consumer, and setup wizard are disabled in memory mode. For PostgreSQL, run migrations before starting the server:

```bash
uv run python scripts/setup_db.py
```

For SQLite, schema migrations are applied automatically on first start.

---

## Source Files

| File | Purpose |
|---|---|
| `src/agent/event_consumer.py` | SQS long-poll loop, filtering, prompt building, delivery |
| `src/agent/investigation_runner.py` | Shared investigation runner (streaming loop, failed-result fallback) |
| `src/agent/event_infra.py` | Create/teardown SQS queue + EventBridge rules |
| `src/agent/context_collectors.py` | Per-event-type boto3 context enrichment |
| `src/agent/monitor_store.py` | In-process service status + DB-backed alerts, notifications, and incident claims; SSE subscriber broadcast |
| `src/agent/init_store.py` | Persist init config to DB-backed `app_config` |
| `src/agent/permission_checker.py` | IAM permission validation |
| `src/api/routers/init.py` | Setup wizard API endpoints |
| `migrations/005_alerts.sql` | PostgreSQL alerts table + indexes |
| `migrations/012_incident_claims.sql` | PostgreSQL incident claim table for atomic deduplication |
