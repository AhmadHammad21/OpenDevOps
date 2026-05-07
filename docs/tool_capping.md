# Tool Response Capping

## What it does

AWS tool responses (CloudWatch Logs, CloudTrail events, ECS task lists, etc.) can return
payloads that are hundreds of kilobytes. Feeding them untruncated into the LLM wastes
tokens and can exhaust the context window mid-investigation.

Tool response capping automatically truncates any tool response that exceeds a
configurable character limit, appending a notice that explains what happened and
suggests how to narrow the query.

## How it works

Every tool registered in `src/agent/core.py` is wrapped with `with_cap()` at startup:

```python
# src/agent/core.py
tools = [with_cap(t) for t in ALL_TOOLS] if settings.tool_response_max_chars > 0 else ALL_TOOLS
```

The cap logic lives in `src/tools/_cap.py`:

- Serialises the result to JSON and measures its length.
- If within the limit → returns the result unchanged.
- If over the limit → returns a replacement dict:

```json
{
  "_capped": true,
  "_original_chars": 184320,
  "_notice": "Response truncated from 184,320 to 40,000 chars to protect the context window. Use more specific filters, shorter time ranges, or pagination to retrieve focused data.",
  "_data": "...first 40,000 chars of the serialised result..."
}
```

The agent sees the truncation notice and knows to refine its query.

## Configuration

Set in `.env` (or leave unset to use the default):

```env
# 0 = disabled (no capping); omit to use the default of 40,000 chars
TOOL_RESPONSE_MAX_CHARS=40000
```

| Value | Behaviour |
|---|---|
| `0` | Capping disabled — all responses pass through unchanged |
| `> 0` | Responses larger than this many characters are truncated |

## Testing it

Run the dedicated unit tests:

```bash
uv run pytest tests/test_tools/test_cap.py -v
```

To trigger capping manually:

```python
from tools._cap import cap_tool_result

big = {"events": ["x"] * 10_000}
result = cap_tool_result(big, max_chars=100)
print(result["_capped"])      # True
print(result["_notice"])
```

Or with a real tool response — set `TOOL_RESPONSE_MAX_CHARS=1` in `.env` and fire
any CloudWatch query; the agent's reply will reference the truncation notice.

## When capping does NOT fire

- Non-dict return values are passed through unchanged (e.g., plain strings).
- If `TOOL_RESPONSE_MAX_CHARS=0` the wrapper is never applied.
- The cap applies only to what the LLM sees; the full raw response is **not** logged
  or persisted — the agent stores only what it actually received.
