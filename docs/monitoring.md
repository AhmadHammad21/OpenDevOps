# Monitoring Dashboard

The Monitoring page shows a live feed of every incident detected and investigated by the agent — whether triggered by the proactive poller, an EventBridge event, or a manual test. This page explains both the UI and the two detection systems that feed it.

---

## Detection Modes

OpenDevOps Agent has two complementary detection modes. Both write to the same `/monitoring` page and Slack channel.

| | Proactive Polling | Event-Driven (EventBridge → SQS) |
|---|---|---|
| **How it works** | Agent polls CloudWatch alarms + Lambda error rates on a timer | AWS fires EventBridge rules → SQS → consumer → agent |
| **Setup** | Set `POLL_INTERVAL_MINUTES` in `.env` | Create infrastructure via Settings → AWS Configuration |
| **Detection latency** | Up to N minutes (your poll interval) | 2–5 min for alarm-based events; near-instant for direct events (ECS, RDS, GuardDuty) |
| **CloudWatch alarm required** | No — reads Lambda error rate directly via API | Yes — EventBridge only fires when an alarm changes state |
| **Works without AWS setup** | Yes — no SQS/EventBridge needed | No — requires SQS queue + EventBridge rules |
| **Event types covered** | CloudWatch alarms in ALARM state + Lambda error rates | CloudWatch alarms, ECS task failures, Lambda async errors, RDS events, EC2 state changes, CodePipeline failures, GuardDuty findings, AWS Health events |
| **Appears in /monitoring** | Yes | Yes |
| **Slack notifications** | Yes (if `SLACK_WEBHOOK_URL` set) | Yes (if `SLACK_WEBHOOK_URL` set) |

**Recommendation:** enable both. Polling works immediately with zero AWS infrastructure and is faster for Lambda error detection. Event-driven catches a wider surface area (ECS, RDS, EC2, GuardDuty, etc.) once infrastructure is created.

---

## Proactive Polling

### What it does

Every `POLL_INTERVAL_MINUTES` minutes, the background poller runs two checks:

1. **CloudWatch alarms** — fetches every alarm currently in `ALARM` state; runs a full agent investigation for each new one
2. **Lambda error rates** — checks the last-hour error rate for up to 20 Lambda functions; runs an investigation for any function above `POLL_ERROR_THRESHOLD`%

### Flow

```
Background timer fires every N minutes
  → get_alarms("ALARM")        — any alarm in ALARM state?
  → list_lambda_functions()    — check each function's error rate
      → error_rate > threshold?
          → agent.ainvoke()    — full ReAct investigation
              → add_alert()    — persists to alerts table → /monitoring
              → notify_slack() — posts to Slack
```

### When to use

- You want incident detection with zero AWS infrastructure setup
- Fast Lambda error detection (1-minute polling catches errors in ~1–2 minutes)
- You don't have CloudWatch alarms pre-configured

### Configuration

```bash
POLL_INTERVAL_MINUTES=5       # 0 = disabled (default)
POLL_ERROR_THRESHOLD=5.0      # Lambda error rate % to trigger investigation
POLL_REINVESTIGATE_HOURS=1    # cooldown — skip re-investigating the same alarm within N hours
```

Set `POLL_INTERVAL_MINUTES=0` to disable entirely. The poller only starts when this value is greater than zero.

### Deduplication

An in-memory map (`_last_investigated`) tracks when each alarm or Lambda was last investigated. If the cooldown (`POLL_REINVESTIGATE_HOURS`) hasn't elapsed, the trigger is skipped. This resets on process restart — intentionally, so startup re-checks everything.

### Source

`src/agent/poller.py` — see also [slack_and_polling.md](slack_and_polling.md) for Slack integration details.

---

## Event-Driven Detection

### What it does

An SQS long-poll consumer receives real AWS infrastructure events forwarded by EventBridge rules, runs a deterministic context-collection pass, then runs a full agent investigation.

### Flow

```
AWS service emits an event (ECS task stopped, Lambda errors, RDS failover…)
  → CloudWatch / EventBridge evaluates matching rule
  → SQS queue (opendevops-agent-events)
      → event_consumer_loop() — long-polls every 20s
          → _is_real_failure() — filters noise (e.g. EC2 "running", healthy RDS events)
          → collect_context()  — deterministic boto3 pre-fetch (logs, metrics, config)
          → agent.ainvoke()    — full ReAct investigation
              → add_alert()    — persists to alerts table → /monitoring
              → SNS publish    — fan-out to email, Lambda, etc.
              → notify_slack() — posts to Slack
```

### When to use

- You want broad coverage beyond Lambda (ECS, RDS, EC2, GuardDuty, AWS Health)
- You already have CloudWatch alarms configured on your resources
- You want SNS fan-out for email/PagerDuty/custom integrations

### Why 2–5 minutes for alarm-based events?

CloudWatch alarm-triggered EventBridge events have an inherent delay:

1. Lambda generates errors → CloudWatch collects metric (~1 min)
2. Alarm evaluation period fires (minimum 60s period)
3. Alarm transitions OK → ALARM → EventBridge fires (near-instant)
4. SQS consumer picks up message (up to 20s long-poll)
5. Agent investigation runs (30–90s)

Direct events (ECS task stopped, GuardDuty finding, RDS failover) skip the alarm evaluation and arrive in seconds.

### Event types and rules

| EventBridge Rule | Events captured |
|---|---|
| `opendevops-alarm-state` | CloudWatch Alarm state changes (OK → ALARM) |
| `opendevops-lambda-failure` | Lambda async invocation failures |
| `opendevops-lambda-throttle` | Lambda throttling errors |
| `opendevops-ecs-task-stopped` | ECS task stopped with non-zero exit / OOM |
| `opendevops-ec2-state` | EC2 instance terminated |
| `opendevops-rds-events` | RDS failures, failovers, recovery |
| `opendevops-health` | AWS Health personal health events |
| `opendevops-codedeploy-failure` | CodeDeploy deployment failures |
| `opendevops-guardduty` | GuardDuty findings |

### Aggregate Lambda alarm

When you create infrastructure (Settings → AWS Configuration → Create Infrastructure), the setup wizard also creates a CloudWatch alarm named `opendevops-lambda-errors-aggregate`. This alarm:

- Monitors `AWS/Lambda` `Errors` metric with **no dimensions** — meaning it watches ALL Lambda functions in the account
- Trips when any Lambda has ≥ 1 error in a 60-second window
- Triggers the `opendevops-alarm-state` EventBridge rule → SQS → consumer

This means you get event-driven Lambda coverage without creating per-function alarms.

### Setup

Go to **Settings → AWS Configuration → Create Infrastructure**. This creates:
- SQS queue: `opendevops-agent-events`
- 9 EventBridge rules (all prefixed `opendevops-`)
- Aggregate CloudWatch alarm: `opendevops-lambda-errors-aggregate`

To remove it, click **Teardown**. See [event_detection.md](event_detection.md) for full setup details and IAM permission requirements.

### Context collectors

Before the LLM runs, `collect_context()` makes deterministic boto3 calls to pre-fetch facts about the affected resource (logs, metrics, config). This reduces LLM tool calls by front-loading the most relevant data. Capped at 3,000 chars to stay within token budgets.

### Source

`src/agent/event_consumer.py`, `src/agent/event_infra.py`, `src/agent/context_collectors.py` — see also [event_detection.md](event_detection.md).

---

## SQS vs SNS — What Each Does

These are often confused. They serve different roles:

| | SQS | SNS |
|---|---|---|
| **Direction** | Input to agent | Output from agent |
| **Role** | Receives EventBridge events for the agent to process | Fan-out investigated results to subscribers |
| **Who writes to it** | AWS EventBridge rules | Agent, after investigation completes |
| **Who reads from it** | `event_consumer_loop()` | Email, Lambda, Telegram, custom HTTP endpoints |
| **Required** | Yes, for event-driven detection | No — optional output channel |

SQS is the inbox. SNS is the outbox. You need SQS for event-driven detection; SNS is optional and only relevant if you want to route investigation results to external systems beyond Slack.

---

## Choosing Between the Two

| Scenario | Recommendation |
|---|---|
| Getting started, no AWS setup | Polling only (`POLL_INTERVAL_MINUTES=5`) |
| Lambda error monitoring only | Polling — faster and simpler |
| ECS, RDS, EC2, GuardDuty coverage | Event-driven required |
| Already have CloudWatch alarms | Event-driven — reuses your existing alarms |
| Want fastest Lambda detection | Both — polling at 1 min catches errors before the alarm trips |
| Want email/PagerDuty alerts | Event-driven + SNS |

---

## Testing the Pipeline

**Test polling** — set `POLL_INTERVAL_MINUTES=1`, trigger Lambda errors, wait ~1–2 minutes.

**Test event-driven (fast — bypasses CloudWatch):**
```bash
uv run python scripts/test_pipeline.py --function my-function
```
Pushes a synthetic alarm event directly to SQS. Result appears on `/monitoring` in ~60–90s.

**Test event-driven (real path — waits for alarm):**
```bash
uv run python scripts/test_pipeline.py --function my-function --lambda-only
```
Invokes the Lambda with a bad payload, then exits. The `opendevops-lambda-errors-aggregate` alarm trips in ~1–2 minutes and fires the full EventBridge → SQS → agent path.

---

## Monitoring Dashboard UI

### Incident Feed

Each alert card shows:

- **Confidence badge** — `HIGH` (red), `MEDIUM` (amber), or `LOW` (grey)
- **Service** — the affected AWS service and resource name
- **Error** — the root cause summary from the agent
- **Time** — when the event was detected
- **SNS badge** — shown if the finding was published to SNS

Alerts are sorted by most recent first. Click any card to open the Alert Detail page.

### Alert Detail Page

Shows the full investigation result:

- Root cause in a highlighted panel
- Resolution steps produced by the agent
- Timestamp and SNS notification status

**Investigate button** — opens a new chat session with a pre-seeded prompt for deeper analysis. The prompt auto-submits when the chat page loads.

### Service Health Panel

The top of the page shows tracked services and their last-known status (`healthy`, `error`, `unknown`). Updated in-memory each time the event consumer processes an event for a service.

### Send Test Event (admin only)

The **Send test event** button in the Monitoring page header pushes a synthetic Lambda alarm to SQS. Requires event infrastructure to be set up. Shows an error toast if `sqs_queue_url` is not configured.

---

## API

```
GET  /api/monitoring/alerts?limit=50   → list recent alerts
GET  /api/monitoring/alerts/{id}       → single alert detail
GET  /api/monitoring/services          → service health summary
```

---

## Source Files

| File | Purpose |
|---|---|
| `frontend/src/pages/MonitoringPage.tsx` | Live incident feed UI |
| `frontend/src/pages/AlertDetailPage.tsx` | Alert detail + investigate deeplink |
| `src/api/routers/monitoring.py` | REST endpoints |
| `src/agent/monitor_store.py` | In-memory service status + alert persistence |
| `src/agent/poller.py` | Proactive polling loop |
| `src/agent/event_consumer.py` | SQS long-poll consumer |
| `src/agent/event_infra.py` | Create/teardown SQS + EventBridge + alarm |
| `src/agent/context_collectors.py` | Per-event-type boto3 context enrichment |
| `scripts/test_pipeline.py` | Pipeline test script (direct SQS push or Lambda invoke) |

---

## Related Documentation

- [event_detection.md](event_detection.md) — event-driven architecture deep dive, IAM permissions, context collectors
- [slack_and_polling.md](slack_and_polling.md) — Slack integration, polling configuration, deduplication
