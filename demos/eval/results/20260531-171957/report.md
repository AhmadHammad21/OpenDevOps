# OpenDevOps Eval — 2026-05-31 17:21

**1/1 root causes found** . median 45.6s . total $0.0014

| scenario | pass | latency | tools | cost | model | root cause |
|---|---|---|---|---|---|---|
| 001_lambda_crashing | PASS | 45.6s | 11 | $0.0014 | `openrouter/google/gemma-4-26b-a4b-it` | SYSTEM_CHANGE |

## Per-scenario detail

### 001_lambda_crashing — PASS

**Agent's root cause:** The Lambda function 'opendevops-demo-crashing' is failing with a 100% error rate because it expects a 'user_id' key in the event payload that is missing. This appears to be due to a recent deployment (based on CloudTrail events) or a change in the upstream event schema.

- root_cause_category match: SYSTEM_CHANGE
- services match: ['Lambda']
- evidence keywords 2/2 found: ['KeyError', 'user_id']
- called expected tool(s): ['describe_log_groups', 'query_logs_insights', 'get_lambda_error_rate']
