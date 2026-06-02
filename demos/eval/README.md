# OpenDevOps Eval

A small, reproducible benchmark for the investigation agent. Each scenario is
a real AWS / Azure incident with a known root cause; the runner stands up the
broken state, asks the agent to investigate, scores the agent's answer against
ground truth, then tears down.

```
                       ┌─────────────┐
demos/aws/e2_…  ──────►│  setup()    │ create broken state
                       └──────┬──────┘
                              │
                       ┌──────▼──────┐
prompt.txt    ────────►│  POST /chat │ stream SSE, collect tool calls
                              │       │ + the submit_investigation args
                       └──────┬──────┘
                              │
                       ┌──────▼──────┐
ground_truth.json ────►│  score()    │ root cause match + evidence overlap +
                       └──────┬──────┘ services + tool-call efficiency
                              │
                       ┌──────▼──────┐
                       │  teardown() │ remove what setup created
                       └─────────────┘
```

## Why

The README's numbers (*"18/20 root causes found, $0.018/incident, 42s median"*)
come from running this. Lock the eval in CI and every PR shows whether the
agent got smarter, cheaper, or slower. It's also the floor for "OpenDevOps Eval
v2" — every scenario you add increases coverage.

## Running

```bash
# Prereqs: agent dev server up at :8000 (uv run dev) AND AWS creds with permission
# to create the tiny scenario resources (Lambdas, throwaway IAM roles, etc.).
# Azure scenarios need a logged-in `az` CLI session.

uv run python demos/eval/run.py                           # all scenarios, real /chat + real cloud
uv run python demos/eval/run.py --scenario 001            # by id prefix
uv run python demos/eval/run.py --skip-setup              # use already-up state (fast iter)
uv run python demos/eval/run.py --skip-teardown           # leave state up for inspection
uv run python demos/eval/run.py --base-url http://localhost:8000   # default — point at the deployed product
uv run python demos/eval/run.py --token <JWT>             # auth-required deployments
uv run python demos/eval/run.py --setup-profile default   # use a write-capable AWS profile for setup/teardown only
                                                          # (the agent itself keeps using whatever the .env says)

# Output: console table + demos/eval/results/<timestamp>/report.md
#                       + per-scenario subprocess logs in the same dir
```

### Read-only vs write-capable AWS profiles

Best practice: the **agent runtime** uses a read-only IAM principal (least
privilege — that's what the docs ship). But the **eval setup/teardown** has to
create and delete Lambdas, IAM roles, ECS tasks, etc., which needs write
permissions.

The runner supports this split: keep the agent's read-only key in `.env`, then
run the eval with `--setup-profile default` (or any other write-capable
profile in `~/.aws/credentials`). The flag rewrites the AWS env for the
setup/teardown subprocesses *only* — the agent's `/chat` call uses the
original (read-only) creds.

```bash
# .env has AWS_PROFILE=devops-agent-readonly (the agent uses this)
# ~/.aws/credentials has [default] with full perms
uv run python demos/eval/run.py --setup-profile default
```

If setup fails with `AccessDeniedException` on `iam:CreateRole` /
`lambda:DeleteFunction` / similar, this is what you want.

## Adding a scenario

1. Make sure your scenario has a `setup`/`teardown` script under `demos/aws/` or
   `demos/azure/` (the existing ones already follow this pattern).
2. `mkdir demos/eval/scenarios/00N_short_name/`.
3. Drop a `scenario.json` in it:

```json
{
  "name": "Lambda crashing with unhandled exception",
  "cloud": "aws",
  "demo": "demos/aws/e2_lambda_crashing.py",
  "prompt": "opendevops-demo-crashing has a high error rate, investigate",
  "timeout_seconds": 180,
  "ground_truth": {
    "root_cause_category": "COMPONENT_FAILURE",
    "services_affected": ["Lambda"],
    "evidence_keywords": ["KeyError", "user_id"],
    "expected_tools_any_of": ["get_log_events", "describe_log_groups", "query_logs_insights"]
  }
}
```

That's it. The runner picks it up automatically.

## Ground-truth schema

| Field | Type | What it pins |
|---|---|---|
| `root_cause_category` | string OR list[string] of `SYSTEM_CHANGE` / `INPUT_ANOMALY` / `RESOURCE_LIMIT` / `COMPONENT_FAILURE` / `DEPENDENCY_ISSUE` / `UNKNOWN` | The category the agent must classify the incident as. A list accepts any of the values — useful when an incident is defensibly classifiable in more than one way (e.g. a Lambda crashing on a missing key is both `COMPONENT_FAILURE` and `SYSTEM_CHANGE`). Matches the `submit_investigation` enum. |
| `services_affected` | list[str] | Substring match against the agent's `services_affected` array. Tolerant: `["Lambda"]` matches `["AWS Lambda"]`. |
| `evidence_keywords` | list[str] | Keywords that must appear in the agent's `evidence` text (case-insensitive). Pin the cause — e.g. `["KeyError", "user_id"]` for a Python traceback. |
| `expected_tools_any_of` | list[str] | The agent must call at least one of these tools. Pin the methodology — e.g. log inspection for a runtime error. |

## Scoring

A scenario passes if ALL of:

- `root_cause_category` matches exactly.
- ≥ 50% of `evidence_keywords` appear in the agent's evidence (Jaccard floor).
- ≥ 1 service in `services_affected` shows up in the agent's output (case-/space-insensitive substring).
- ≥ 1 tool in `expected_tools_any_of` was called.

The runner also reports soft metrics: latency, input/output tokens, cost (USD),
tool-call count. Useful for tracking regressions even when accuracy stays at
100%.

## Cost guard

Each scenario creates a tiny amount of AWS state (~$0.001 per run for the
Lambda-based ones; ECS/RDS scenarios run a few cents per minute they're up).
The runner aborts the suite if any scenario's setup fails so you don't leak
resources. `--skip-teardown` leaves them up — remember to clean those out
yourself.

## Not a unit test

This is an **integration** eval. It hits real AWS / Azure, real LLM API
spend, and real network. Don't put it in `pytest`. Run it nightly in a
dedicated CI lane, or manually before releases.

The pure scoring functions in `scoring.py` ARE unit-testable — see
`apps/backend/tests/test_eval/test_scoring.py` (TODO if you want
coverage on the scorer itself).
