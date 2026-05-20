# Slack Notifications & Proactive Polling

## Overview

OpenDevOps Agent can send investigation results to a Slack channel in two modes:

- **Reactive** — posts automatically after every completed investigation
- **Proactive** — a background poller detects CloudWatch alarms and Lambda error spikes, runs investigations autonomously, and posts without any human trigger

---

## Polling vs Event-Driven — which do you need?

| | Proactive Polling | Event-Driven (EventBridge → SQS) |
|---|---|---|
| **Setup required** | Just set `POLL_INTERVAL_SECONDS` in `.env` | Create AWS infra via Settings → AWS Configuration |
| **Detection latency** | Up to N minutes (your poll interval) | Near real-time (~seconds after event fires) |
| **CloudWatch alarm required** | No — checks Lambda error rates directly | Yes — EventBridge only fires when an alarm trips |
| **Works out of the box** | Yes | Requires CloudWatch alarms on your resources |
| **Results in /monitoring** | Yes | Yes |
| **Slack notifications** | Yes | Yes |

**Recommendation:** enable both. Polling works immediately with zero AWS setup and catches Lambda error rate spikes. Event-driven is faster and catches a wider range of AWS failures (ECS, RDS, EC2, GuardDuty, etc.) once you have CloudWatch alarms in place. They are complementary — both write to the same `/monitoring` page and Slack channel.

---

## Configuration

Add these to your `.env`:

```bash
# Required to enable either mode
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../xxx

# Proactive polling (leave at 0 to disable)
POLL_INTERVAL_SECONDS=300     # how often to check; 0 = reactive only
POLL_ERROR_THRESHOLD=5.0      # Lambda error rate % that triggers an investigation
POLL_REINVESTIGATE_HOURS=1    # cooldown — don't re-investigate the same alarm within N hours
```

How to get a webhook URL: [api.slack.com/apps](https://api.slack.com/apps) → your app → **Incoming Webhooks** → **Add New Webhook to Workspace**.

---

## Reactive Mode

Every time the agent finishes an investigation it calls the `submit_investigation` tool as its structured final answer (see [When is `submit_investigation` called?](#when-is-submit_investigation-called) below). The moment that tool call is recorded, `_maybe_notify_slack` in `src/api/routers/chat.py` fires and posts the result to Slack.

**Flow:**
```
User message → agent reasons + calls AWS tools → calls submit_investigation
    → _save_turn (persist to DB)
    → _maybe_notify_slack (post to Slack if SLACK_WEBHOOK_URL is set)
    → SSE "done" event sent to browser
```

One investigation = one Slack message. If the agent does not reach a conclusion (e.g. hit the tool call limit), no message is sent.

---

## Proactive Mode

When `POLL_INTERVAL_SECONDS > 0`, the app starts a background `asyncio` task (`polling_loop` in `src/agent/poller.py`) on startup. Every N seconds it runs two checks:

### 1. CloudWatch Alarms
Calls `get_alarms("ALARM")` and iterates over every alarm currently in ALARM state. For each one:
- Builds a prompt with the alarm name, metric, and reason
- Runs a full agent investigation (`agent.ainvoke`)
- Posts the result to Slack

### 2. Lambda Error Rates
Calls `list_lambda_functions` (capped at 20 functions) and checks each one's error rate over the last hour via `get_lambda_error_rate`. If the rate exceeds `POLL_ERROR_THRESHOLD`:
- Builds a prompt describing the error rate
- Runs a full agent investigation
- Posts the result to Slack
- Saves the result to the `alerts` table — visible in the `/monitoring` page

### Dedup
The poller uses canonical incident keys and an atomic database claim before the agent runs. If the cooldown (`POLL_REINVESTIGATE_HOURS`) has not elapsed, the alarm or function is skipped. Autonomous polling requires SQLite or PostgreSQL; memory mode does not start the poller.

### Thread isolation
Boto3 calls in the poller run inside a bounded `ThreadPoolExecutor(max_workers=4)` named `poller`. This prevents poller threads from consuming the default executor used by the rest of the app, and caps concurrent boto3 calls to four threads even if multiple alarms fire simultaneously.

---

## When is `submit_investigation` called?

`submit_investigation` is a **tool** registered on the agent alongside the 19 AWS tools. The system prompt instructs the agent:

> "When you have gathered sufficient evidence and reached a conclusion, you MUST call the `submit_investigation` tool with all fields populated. Do not write a JSON block in free text — call the tool instead."

So the agent calls it exactly like any other tool — it decides when it has enough evidence, then emits a tool call with the full structured result as arguments. This approach:

- **Enforces schema** — LangChain converts the `Literal` type annotations on `root_cause_category` and `confidence` to JSON Schema `enum` constraints, so the LLM can't produce invalid values
- **Makes the result inspectable** — the args are captured in `tool_calls_log`, saved to the DB (`tool_calls` table), and visible in the UI's tool call inspector
- **Triggers Slack** — `_maybe_notify_slack` scans `tool_calls_log` for a `submit_investigation` entry; no special signal needed

The function itself just returns `"Investigation result recorded."` — the real value is in the structured args the LLM was forced to populate.

If the LLM completes the ReAct loop without ever calling `submit_investigation` (a failure mode seen with some weaker models), the investigation runner synthesizes a `_status: failed` result so the alert is always persisted to the monitoring page instead of being silently dropped.

---

## Message Format

Messages are sent as Slack [Block Kit](https://api.slack.com/block-kit) attachments. The sidebar color is keyed to the root cause category:

| Category | Color |
|---|---|
| `SYSTEM_CHANGE` | Orange |
| `INPUT_ANOMALY` | Blue |
| `RESOURCE_LIMIT` | Red |
| `COMPONENT_FAILURE` | Dark red |
| `DEPENDENCY_ISSUE` | Purple |
| `UNKNOWN` | Grey |

Each message includes: root cause category, confidence (with emoji), summary, evidence bullets, numbered mitigation steps, affected services, and a session ID footer.

---

## Testing

Send a test message without running a full investigation:

```bash
uv run python tests/integration/test_slack.py
```

This posts a sample `RESOURCE_LIMIT` investigation result to your configured webhook.

---

## Source Files

| File | Purpose |
|---|---|
| `src/integrations/slack_webhook.py` | Block Kit payload builder + HTTP post |
| `src/agent/poller.py` | Background polling loop |
| `src/api/routers/chat.py` | `_maybe_notify_slack` — reactive trigger |
| `src/api/app.py` | Lifespan: starts/stops the polling task |
| `src/tools/final_answer.py` | `submit_investigation` tool definition |
| `tests/integration/test_slack.py` | Standalone webhook test |
