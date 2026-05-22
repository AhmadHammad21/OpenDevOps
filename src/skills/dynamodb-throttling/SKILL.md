---
name: dynamodb-throttling
description: Investigate DynamoDB throttling — provisioned capacity exceeded, hot partitions, GSI limits surfacing as upstream Lambda/app errors
---

## DynamoDB Throttling Investigation

DynamoDB throttling rarely shows up as a DynamoDB alarm — it usually surfaces as
errors in the **caller** (a Lambda, ECS service, or app). Treat upstream errors as
a symptom and trace down to the table.

### Step 1 — Find the throttling exception in the caller's logs

- For a Lambda caller: `get_log_events(log_group="/aws/lambda/<fn>", filter_pattern="ProvisionedThroughputExceeded")`, or `get_lambda_error_rate(fn)` to confirm the spike
- For ECS: `get_ecs_task_logs(...)`
- Look for these exception strings — they name the cause directly:
  - `ProvisionedThroughputExceededException` → provisioned table/index over its capacity
  - `ThrottlingException` / `Throughput exceeds the current capacity` → on-demand table hitting its scaling ceiling, or a hot partition
  - `Rate of requests exceeds the allowed throughput` → GSI throttling

### Step 2 — Identify the table and its capacity mode

Use the bash tool (DynamoDB has no structured tool):

- `run_bash_command("aws dynamodb describe-table --table-name <table>")`
- Read:
  - `BillingModeSummary.BillingMode` — `PROVISIONED` vs `PAY_PER_REQUEST`
  - `ProvisionedThroughput.ReadCapacityUnits` / `WriteCapacityUnits` — the hard ceiling if provisioned
  - `GlobalSecondaryIndexes[].ProvisionedThroughput` — GSIs have their **own** capacity; a throttled GSI throttles the whole write

### Step 3 — Confirm with CloudWatch metrics

Use `get_metric_data` on namespace `AWS/DynamoDB`, dimension `TableName`:

- `ConsumedReadCapacityUnits` / `ConsumedWriteCapacityUnits` — actual usage
- `ReadThrottleEvents` / `WriteThrottleEvents` — the throttle count (the smoking gun)
- `ProvisionedReadCapacityUnits` / `ProvisionedWriteCapacityUnits` — the configured ceiling
- Compare consumed vs provisioned in the incident window: if consumed brushes the ceiling and throttle events climb, it's a capacity problem

### Step 4 — Distinguish capacity vs hot partition

- If **total** consumed capacity is well below provisioned but throttling still occurs → **hot partition**: traffic is concentrated on a few partition-key values, so one partition's share of capacity is exhausted while the table average looks fine
- If total consumed is at/above provisioned → straightforward under-provisioning or a traffic spike

### Step 5 — Check what changed

`lookup_cloudtrail_events(hours=24)` and filter for:
- `UpdateTable` — capacity lowered, or switched PAY_PER_REQUEST → PROVISIONED
- Recent `UpdateFunctionCode` on the caller — a new code path issuing far more reads/writes

### Common Root Causes

| Cause | Signal | Fix |
|---|---|---|
| Under-provisioned table | Consumed near provisioned ceiling; `WriteThrottleEvents` > 0 | Raise capacity, enable auto-scaling, or switch to on-demand |
| GSI throttling | Throttles with table capacity spare; GSI has low capacity | Raise the GSI's capacity (it's separate from the table) |
| Hot partition | Throttles while table-average consumption is low | Improve partition-key cardinality / add a write-sharding suffix |
| Burst after on-demand idle | On-demand table, sudden spike past the adaptive ceiling | Pre-warm, or set provisioned + auto-scaling for predictable load |
| Capacity recently lowered | `UpdateTable` in CloudTrail before the incident | Restore previous capacity |

### Mitigation Steps (read-only — document for human action)

1. **Under-provisioned:** raise RCU/WCU to cover peak consumed plus headroom, or enable application auto-scaling; for spiky/unpredictable load consider `PAY_PER_REQUEST`
2. **GSI:** raise the index's own provisioned capacity — it does not inherit the table's
3. **Hot partition:** redesign the partition key for higher cardinality, or add a sharding suffix and scatter-gather on read
4. **Caller side:** ensure the SDK's exponential-backoff retry is enabled; batch writes (`BatchWriteItem`) to smooth bursts
