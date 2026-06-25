# Replayable Evidence Pack

## What it does

Every investigation ends with the agent calling `submit_investigation`, whose arguments
are the structured conclusion. The evidence pack is a read-only view over that conclusion
and the tool calls that produced it: it groups the investigation's **ranked hypotheses**,
ties each piece of cited evidence back to the tool call that produced it, surfaces the
exact query/command that ran, and builds a deterministic AWS-console deeplink so a human
can reproduce the agent's steps.

It is pure presentation — it reads already-persisted data and never mutates state, changes
the SSE contract, or touches the bash allowlist.

## Endpoint

```
GET /api/sessions/{session_id}/evidence
```

The `/api/` prefix keeps the SPA fallback catch-all from intercepting the request. The
router (`src/api/routers/evidence.py`) calls `db.get_evidence(session_id)` for the region +
raw tool-call rows, then `build_evidence_pack()` (in `opendevops_core/agent/evidence.py`)
assembles the response. The conclusion is read from the `tool_calls` row whose
`tool_name = 'submit_investigation'` — **not** from the `findings` table, which is currently
an unwritten placeholder.

### Response shape

```json
{
  "session_id": "…",
  "aws_region": "us-east-1",
  "has_conclusion": true,
  "root_cause_category": "RESOURCE_LIMIT",
  "root_cause_summary": "…",
  "confidence": "HIGH",
  "hypotheses": [
    {
      "hypothesis": "…",
      "confidence": "HIGH",
      "evidence": [
        { "text": "…concrete finding…", "tool_call_id": "tc-3" }
      ]
    }
  ],
  "tool_calls": [
    {
      "id": "tc-3",
      "index": 3,
      "tool": "query_logs_insights",
      "service": "CloudWatch Logs",
      "args": { "…": "…" },
      "result": "…",
      "error": null,
      "command": "fields @timestamp, @message | filter …",
      "console_url": "https://us-east-1.console.aws.amazon.com/cloudwatch/home#…",
      "created_at": "…"
    }
  ]
}
```

## How linking, commands, and deeplinks work

- **Evidence → tool call** — each evidence string is matched to the supporting tool call by
  a deterministic best-effort substring count over the call's distinctive arg identifiers
  (the tool name is only a tie-breaker). `tool_call_id` is `null` when nothing matches.
- **Exact command** — `command` is populated only for the tools that ran a verbatim string:
  the Logs Insights query (`query_logs_insights`) and the bash CLI command
  (`run_bash_command`, e.g. `aws`/`az`/`kubectl`). Azure has no console deeplink by design,
  so the command string **is** the replay artifact.
- **Console deeplink** — `console_url` is a deterministic AWS-console URL for CloudWatch
  alarms/metrics/logs, Logs Insights, Lambda, EC2, and RDS calls; `null` when the tool has
  no console target or no region is known.

## Backward compatibility

When a conclusion has no `hypotheses` (investigations from before the ranked-hypotheses
schema), the builder synthesizes a single hypothesis from the legacy `root_cause_summary` +
flat `evidence[]` so older sessions still render.

## UI

A **Evidence** button in the chat header opens a slide-over `EvidencePanel` that renders the
grouped hypotheses and replay cards, with copy-to-clipboard and a full JSON export. See
[ui.md](ui.md).

## Testing it

```bash
uv run pytest tests/test_api/test_evidence.py          # endpoint shape, grouping, linking, deeplinks
uv run pytest tests/test_tools/test_evidence_pack.py   # builder, console encoder, schema
```
