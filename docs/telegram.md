# Telegram Notifications

OpenDevOps Agent can send investigation results to a Telegram chat via a bot. Both the event consumer (EventBridge → SQS) and the proactive poller deliver to Telegram alongside Slack — they are independent and can both be active at the same time.

---

## Quick Setup

### 1. Create a bot

Open Telegram and message **@BotFather**:

```
/newbot
```

Follow the prompts — you'll receive a token like:

```
123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 2. Get your chat ID

Add the bot to the group or channel you want alerts in, then send any message to it and open this URL in your browser (replace the token):

```
https://api.telegram.org/bot<TOKEN>/getUpdates
```

Find `"chat": { "id": -100123456789 }` in the response. **Group/channel IDs are negative numbers.**

For a personal chat: message the bot directly, then check `getUpdates` — your personal chat ID is a positive number.

### 3. Add to `.env`

```bash
TELEGRAM_BOT_TOKEN=123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=-100123456789
```

Restart the server. OpenDevOps will start delivering to Telegram immediately.

---

## Verify it works

Go to **Settings → Integrations → Telegram** and click **Send test message**. You should see a formatted test investigation appear in your chat within a few seconds.

You can also call the API directly:

```bash
curl -X POST http://localhost:8000/api/integrations/telegram/test \
  -H "Authorization: Bearer <your-token>"   # omit if auth is disabled
```

---

## Message format

Messages use Telegram's **HTML parse mode**. A successful investigation looks like:

```
🔍 OpenDevOps — Investigation Complete

🔴 HIGH confidence  ·  RESOURCE_LIMIT

Root Cause
Lambda exhausted memory under burst traffic.

Services affected: Lambda, CloudWatch

Evidence
• MemoryUtilization reached 99%
• OOM errors spiked in CloudWatch logs

Mitigation Steps
1. Increase Lambda memory to 1024 MB
2. Add CloudWatch memory alarm at 80%

Session 1a2b3c4d
```

A failed investigation (agent hit the tool call limit or errored) looks like:

```
⚠️ OpenDevOps — Investigation Failed

Service: payment-service
Error: Investigation failed: agent timeout after 120s

Session 1a2b3c4d
```

---

## Delivery tracking

Every Telegram notification is recorded in the `alert_notifications` table:

```sql
SELECT channel, status, sent_at
FROM alert_notifications
WHERE alert_id = '<alert-uuid>'
  AND channel = 'telegram';
```

The **Monitoring → alert detail** page shows this under "Notified via" with a green check (delivered) or red X (failed).

---

## Combining Slack and Telegram

Both channels fire independently. Set both `SLACK_WEBHOOK_URL` and `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` to receive notifications in both places. Each delivery is tracked separately in `alert_notifications`.

---

## Configuration reference

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Yes | Target chat/group/channel ID |

Both must be set. If either is missing, Telegram delivery is silently skipped.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| "Not configured" badge in Settings | One or both env vars missing or `(not set)` | Add both vars to `.env` and restart |
| Test message returns 400 | Vars not loaded yet | Verify `.env` has both vars; restart the server |
| Message not received | Wrong chat ID, or bot not in the group | Re-run `getUpdates` to confirm chat ID; make sure the bot is a member of the group/channel |
| `chat not found` in server logs | Chat ID is wrong or bot was never added | Add bot to the group first, then send a message before checking `getUpdates` |
| Notifications show as `failed` in alert detail | Bot API returned non-200 | Check server logs for the exact Telegram error message |

---

## Source files

| File | Purpose |
|---|---|
| `src/integrations/telegram.py` | Bot API client — message builder + HTTP delivery |
| `src/agent/event_consumer.py` | Delivers to Telegram after each event-driven investigation |
| `src/agent/poller.py` | Delivers to Telegram after each polling investigation |
| `src/api/routers/integrations.py` | `POST /api/integrations/telegram/test` endpoint |
| `src/config/appsettings.py` | `telegram_bot_token` + `telegram_chat_id` settings |
| `tests/integration/test_telegram.py` | Unit tests for message rendering and delivery |
