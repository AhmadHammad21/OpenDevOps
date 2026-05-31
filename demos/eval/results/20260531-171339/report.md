# OpenDevOps Eval — 2026-05-31 17:15

**0/1 root causes found** . median 48.9s . total $0.0016

| scenario | pass | latency | tools | cost | model | root cause |
|---|---|---|---|---|---|---|
| 001_lambda_crashing | FAIL | 48.9s | 8 | $0.0016 | `openrouter/google/gemma-4-26b-a4b-it` | SYSTEM_CHANGE |

## Per-scenario detail

### 001_lambda_crashing — FAIL

**Agent's root cause:** The Lambda function 'opendevops-demo-crashing' is failing with a 100% error rate due to a 'KeyError: 'user_id'' in the code. This is caused by the code attempting to access 'user_id' from the event payload, but the payload being received does not contain this key. This appears to be a code-level issue introduced during a recent creation/deployment of the function.

- root_cause_category='SYSTEM_CHANGE' (expected 'COMPONENT_FAILURE')
- services match: ['Lambda']
- evidence keywords 2/2 found: ['KeyError', 'user_id']
- called expected tool(s): ['describe_log_groups', 'query_logs_insights', 'get_lambda_error_rate']
