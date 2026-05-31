# OpenDevOps Eval — 2026-05-31 17:07

**0/1 root causes found** . median 27.9s . total $0.0000

| scenario | pass | latency | tools | cost | model | root cause |
|---|---|---|---|---|---|---|
| 001_lambda_crashing | FAIL | 27.9s | 7 | — | `openrouter/openai/gpt-4o-mini` | — |

## Per-scenario detail

### 001_lambda_crashing — FAIL
- root_cause_category='' (expected 'COMPONENT_FAILURE')
- no service overlap (agent=[] vs expected=['Lambda'])
- evidence keywords 0/2 (need 50%): missed ['KeyError', 'user_id']
- called expected tool(s): ['get_log_events', 'describe_log_groups', 'query_logs_insights', 'get_lambda_error_rate']
