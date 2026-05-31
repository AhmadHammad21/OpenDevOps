# Eval

A small reproducible benchmark for the investigation agent. Each scenario stands
up a known-bad AWS or Azure state, asks the agent to investigate, then scores the
agent's `submit_investigation` output against ground truth. Use it to:

- Get the README headline number (*"X/N root causes found, $Y/run, Z s median"*).
- Catch regressions when you upgrade models, change prompts, or refactor tools.
- Decide empirically which LLM is reliable enough for production use.

> This is **integration** code — it hits real AWS / Azure and pays real LLM
> costs. It's deliberately *not* a pytest target. Run it nightly in a dedicated
> CI lane, or manually before releases.

---

## Quick start

```bash
# Prereqs:
#   1. Agent dev server running (e.g. `make dev` -> http://localhost:8000).
#   2. An LLM provider configured in apps/backend/.env (any of OPENROUTER_API_KEY,
#      ANTHROPIC_API_KEY, OPENAI_API_KEY, GROQ_API_KEY, GEMINI_API_KEY, or a
#      logged-in Claude Code CLI).
#   3. AWS creds with permission to create the scenario's resources (Lambda,
#      throwaway IAM role). Azure scenarios need a logged-in `az` session.

uv run python demos/eval/run.py                            # all scenarios
uv run python demos/eval/run.py --scenario 001             # one (by id prefix)
uv run python demos/eval/run.py --setup-profile default    # see below
```

Each run writes to `demos/eval/results/<timestamp>/`:

- `report.md` — pass/fail summary, per-scenario detail, soft metrics
  (latency, cost, tokens, tool-call count).
- `results.json` — same data, machine-readable for CI dashboards.
- One log per `setup` / `teardown` subprocess so any cloud error
  (`AccessDeniedException`, etc.) is preserved verbatim even if the terminal
  truncates it.

---

## How it works

```
                                ┌──────────────┐
demos/{aws,azure}/<script>.py   │   setup()    │  create broken state
   (existing scenario scripts) ►│              │
                                └──────┬───────┘
                                       │
                                ┌──────▼───────┐
scenario.json -> prompt        │  POST /chat   │  stream SSE, collect tool calls
                              ►│   (SSE)       │  + submit_investigation args
                                └──────┬───────┘
                                       │
                                ┌──────▼───────┐
scenario.json -> ground_truth ►│   score()     │  category + evidence keywords
                                └──────┬───────┘  + services + tools called
                                       │
                                ┌──────▼───────┐
                                │  teardown()  │  remove what setup created
                                └──────────────┘
```

- Scenarios live under `demos/eval/scenarios/<NNN>_<name>/scenario.json`.
  Each one points at an existing demo script — no Python duplication.
- The runner uses only the stdlib (no extra deps). Discoverable scenarios
  are anything with a `scenario.json` inside `demos/eval/scenarios/`.

---

## Read-only runtime vs write-capable setup

Best practice: the **agent runtime** uses a read-only IAM principal (least
privilege, exactly what `iam_setup.md` ships). The **eval setup/teardown** needs
write permissions to create/delete Lambdas, IAM roles, ECS tasks, etc.

The runner supports the split with `--setup-profile`:

```bash
# .env has AWS_PROFILE=devops-agent-readonly (the agent uses this)
# ~/.aws/credentials has a [default] (or other) profile with full perms
uv run python demos/eval/run.py --setup-profile default
```

The flag rewrites the AWS env for the setup/teardown subprocesses *only* —
the `/chat` call hits the running agent with whatever creds it was started
with. If setup fails with `iam:CreateRole` / `lambda:DeleteFunction`
`AccessDeniedException`, this is the flag you want.

---

## Adding a scenario

1. Make sure your scenario has a `setup`/`teardown` script under `demos/aws/`
   or `demos/azure/` (the existing ones already follow this pattern).
2. `mkdir demos/eval/scenarios/00N_short_name/`.
3. Drop a `scenario.json`:

```json
{
  "name": "Lambda crashing with an unhandled KeyError",
  "cloud": "aws",
  "demo": "demos/aws/e2_lambda_crashing.py",
  "prompt": "opendevops-demo-crashing has a high error rate, investigate",
  "timeout_seconds": 180,
  "propagation_seconds": 30,
  "ground_truth": {
    "root_cause_category": ["COMPONENT_FAILURE", "SYSTEM_CHANGE"],
    "services_affected": ["Lambda"],
    "evidence_keywords": ["KeyError", "user_id"],
    "expected_tools_any_of": [
      "get_log_events", "describe_log_groups",
      "query_logs_insights", "get_lambda_error_rate"
    ]
  }
}
```

The runner picks it up automatically on next invocation.

### Ground-truth schema

| Field | Type | What it pins |
|---|---|---|
| `root_cause_category` | string OR list[string] of `SYSTEM_CHANGE` / `INPUT_ANOMALY` / `RESOURCE_LIMIT` / `COMPONENT_FAILURE` / `DEPENDENCY_ISSUE` / `UNKNOWN` | The category the agent must classify the incident as. A list accepts any of the values — useful when an incident is defensibly classifiable in more than one way (e.g. a Lambda crashing on a missing key is both `COMPONENT_FAILURE` and `SYSTEM_CHANGE`). |
| `services_affected` | list[string] | Substring match against the agent's `services_affected`. Tolerant: `["Lambda"]` matches `["AWS Lambda"]`. |
| `evidence_keywords` | list[string] | ≥ 50% must appear in the agent's `evidence` text (case-insensitive). Pin the cause — e.g. `["KeyError", "user_id"]` for a Python traceback. |
| `expected_tools_any_of` | list[string] | Agent must call ≥ 1. Pins the methodology — e.g. log inspection for a runtime error. |

### Rule of thumb when writing ground truth

> If you'd accept the agent's answer in a code review, the eval should accept
> it too. Use the multi-value `root_cause_category` list whenever the human
> review would say *"yeah, that framing works too."*

---

## Scoring

A scenario passes if **all** of:

- Root-cause category matches (exactly, or matches any value in the list).
- ≥ 1 service in `services_affected` shows up in the agent's output.
- ≥ 50% of `evidence_keywords` appear in the evidence text.
- ≥ 1 tool in `expected_tools_any_of` was called.

Soft metrics — latency, tokens, cost USD, tool-call count — are reported on
every run regardless of pass/fail. Useful for catching regressions even when
accuracy stays at 100%.

The pure scoring functions in `demos/eval/scoring.py` are unit-tested in
`apps/backend/tests/test_eval/test_scoring.py` so a contributor who edits
the scorer sees clear failures rather than mysterious eval regressions.

---

## Cost guard

Each scenario creates a tiny amount of AWS state (~$0.001/run for the
Lambda-based ones; ECS / RDS / VM scenarios run a few cents while up).
The runner always attempts teardown, even when setup fails partway, so
resources don't leak. `--skip-teardown` leaves them up — clean those out
yourself with `python demos/<cloud>/<script>.py teardown`.

---

## Picking the right LLM for your eval

The eval is strict by design — it scores only the structured
`submit_investigation` tool call. **Smaller models routinely skip that step**
and answer in prose, which the eval rightly counts as a fail.

If your model is < 70B params or a budget tier (e.g. `gpt-4o-mini`,
`gemma-4-26b`, Haiku-class), expect false negatives. Switch to:

- `openrouter/anthropic/claude-sonnet-4-6` — strong tool-use, good price
- `openrouter/openai/gpt-4o` — full, not -mini
- `anthropic/claude-opus-4-8` — best quality, direct `ANTHROPIC_API_KEY`

Change in **Settings → Agent config → LLM**, then re-run the eval against
the same scenarios. That's exactly the comparison the framework is for.
