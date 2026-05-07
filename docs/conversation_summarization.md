# Conversation Summarization

## What it does

Long investigations — many tool calls, large log dumps — can push a session's message
history past the LLM's context limit. When that happens the next agent call either
silently drops old messages or throws an error.

Conversation summarization automatically compacts the oldest portion of a session's
message history before each new LLM call. Old messages are replaced with a single
structured summary, preserving recent context intact.

## How it works

`src/agent/summarizer.py` runs `maybe_summarize()` at the start of every chat turn,
before the LangGraph agent call:

```
1. Read current session messages via agent.aget_state()
2. Count total characters
3. If total > SUMMARIZATION_THRESHOLD_CHARS:
   a. Walk from the end, accumulate chars until SUMMARIZATION_KEEP_CHARS is reached
   b. Split only at a HumanMessage boundary (never mid tool-call pair)
   c. Call the LLM with a summarization prompt over the old messages
   d. Replace old messages with one HumanMessage containing the structured summary
   e. Record a usage_event with metadata.summarization = true
4. Proceed with the normal agent call
```

The structured summary follows this template:

```
**Investigating:** <original incident or question>
**Key findings:**
- <finding with specifics — numbers, service names, timestamps>
**Ruled out:** <list or "nothing ruled out yet">
**Current state:** <where the investigation is now>
```

The system prompt is never touched — LangGraph manages it separately.

## Configuration

Set in `.env`:

```env
# Enable/disable summarization entirely (default: true)
SUMMARIZATION_ENABLED=true

# Total session chars that trigger a summarization pass (~15K tokens at 4 chars/token)
SUMMARIZATION_THRESHOLD_CHARS=60000

# How many recent chars to keep intact after compaction (~5K tokens)
SUMMARIZATION_KEEP_CHARS=20000
```

| Variable | Default | Notes |
|---|---|---|
| `SUMMARIZATION_ENABLED` | `true` | Set to `false` to disable completely |
| `SUMMARIZATION_THRESHOLD_CHARS` | `60000` | ~15K tokens; increase for larger context models |
| `SUMMARIZATION_KEEP_CHARS` | `20000` | ~5K tokens of recent context preserved |

## Dashboard tracking

Each summarization run writes a `usage_events` record with:

```json
{
  "summarization": true,
  "messages_removed": 14,
  "chars_removed": 42000
}
```

The `/stats` endpoint (dashboard) exposes two aggregate fields in `summary`:

| Field | Meaning |
|---|---|
| `total_summarizations` | How many times summarization has run across all sessions |
| `total_chars_compacted` | Total characters removed (proxy for tokens saved) |

These power future dashboard widgets ("N sessions compacted, ~X tokens saved").

## Testing it

**Unit test the split logic directly:**

```bash
uv run pytest tests/test_agent/ -v -k "summar"
```

**Trigger it in a real session:**

Temporarily lower the threshold in `.env`:

```env
SUMMARIZATION_ENABLED=true
SUMMARIZATION_THRESHOLD_CHARS=500   # very low — triggers after a couple messages
SUMMARIZATION_KEEP_CHARS=200
```

Then send a few messages in the chat UI. Watch the logs for:

```
[abc12345] summarizer: session=1204 chars, removing 8 msgs (820 chars), keeping 4 msgs
[abc12345] summarizer done: -820 chars, summary 312 chars, 1843ms
```

After that the LangGraph checkpoint for the session will contain the summary
message instead of the old raw exchanges.

**Check dashboard stats (SQLite or Postgres):**

```bash
curl http://localhost:8000/stats | python -m json.tool | grep -A2 summarization
```

## Edge cases

| Scenario | Behaviour |
|---|---|
| Session has < 2 human turns | Summarization skipped — nothing meaningful to compact |
| LLM summarization call fails | Warning logged, session continues without compaction |
| State update fails | Error logged, session continues unchanged |
| `SUMMARIZATION_ENABLED=false` | `maybe_summarize()` returns immediately without any DB or LLM call |
