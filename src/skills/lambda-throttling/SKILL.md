---
name: lambda-throttling
description: Investigate Lambda function throttling — concurrency limits, burst limits, reserved concurrency misconfiguration
---

## Lambda Throttling Investigation

### Step 1 — Identify the throttled function

- Call `get_alarms(state="ALARM")` and look for alarms on `Throttles` metric
- If the function name is known, call `get_error_rate(function_name)` directly
- Otherwise call `list_lambda_functions()` to enumerate candidates

### Step 2 — Confirm throttling vs errors

Lambda reports two distinct failure modes — confirm which you're dealing with:

- **Throttles** (`AWS/Lambda > Throttles`) — requests rejected before execution starts; exit code is 429
- **Errors** (`AWS/Lambda > Errors`) — function executed but threw an exception

Use `get_metric_data` with:
- Namespace: `AWS/Lambda`, Metric: `Throttles`, Dimension: `FunctionName`
- Namespace: `AWS/Lambda`, Metric: `ConcurrentExecutions`, Dimension: `FunctionName`
- Namespace: `AWS/Lambda`, Metric: `ConcurrentExecutions` (no dimension) — account-level

### Step 3 — Check concurrency configuration

Call `get_function_config(function_name)` and look for:

- `ReservedConcurrentExecutions` — if set, this is the hard cap for this function
  - A value of `0` means the function is fully throttled (intentional or misconfiguration)
  - A value lower than current demand causes throttling even if account limit is not hit
- `ProvisionedConcurrencyConfigs` — if missing or underpowered, cold starts under burst may throttle

### Step 4 — Check account-level concurrency limit

Account default is 1000 concurrent executions (region-scoped). If the account-level
`ConcurrentExecutions` metric is near 1000, other functions may be consuming the budget.

Use `run_bash_command("aws lambda get-account-settings")` to see:
- `TotalConcurrentExecutions` — current usage
- `UnreservedConcurrentExecutions` — what's left for functions without reserved concurrency

### Step 5 — Check for recent changes

Call `get_trail_events(hours=2)` and filter for:
- `UpdateFunctionConfiguration` — memory/timeout/concurrency change
- `PutFunctionConcurrency` — reserved concurrency was set (possibly to 0)
- `DeleteFunctionConcurrency` — concurrency limit removed
- `UpdateFunctionCode` — new deployment that may have increased cold-start time

### Step 6 — Check for traffic spike

If no config change is found, the cause is likely demand exceeding capacity:

- Check `Invocations` metric for a spike in the throttling window
- Check upstream triggers: API Gateway (`5XXError`), SQS queue depth (`ApproximateNumberOfMessagesVisible`), EventBridge rule frequency
- Use `run_bash_command("aws sqs get-queue-attributes --queue-url <url> --attribute-names ApproximateNumberOfMessagesVisible")` if SQS-triggered

### Common Root Causes

| Cause | Signal | Fix |
|---|---|---|
| Reserved concurrency set too low | `ReservedConcurrentExecutions` < demand | Raise or remove the reservation |
| Reserved concurrency = 0 | `ReservedConcurrentExecutions = 0` | Remove the 0-cap (likely misconfiguration) |
| Account concurrency limit hit | Account-level `ConcurrentExecutions` near 1000 | Request limit increase via AWS Support |
| Burst limit exceeded | Throttles spike immediately after a cold traffic surge | Use provisioned concurrency or gradual traffic ramp |
| SQS backlog overwhelming function | Large `ApproximateNumberOfMessagesVisible` | Reduce `MaximumConcurrency` on event source mapping or scale up reserved concurrency |

### Mitigation Steps (read-only — document for human action)

1. If `ReservedConcurrentExecutions = 0`: remove the reservation via AWS console or CLI
2. If reservation is set too low: raise it to match peak concurrent demand plus 20% headroom
3. If account limit is hit: open AWS Support case for concurrency increase, or identify and cap noisy-neighbour functions
4. If burst limit: enable provisioned concurrency for the function, or add exponential-backoff retry on the caller side
