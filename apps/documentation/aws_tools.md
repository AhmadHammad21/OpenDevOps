# AWS Tools Reference

All tools are read-only. They wrap boto3 calls and return structured dicts. Every tool
is decorated with `@tool_cached` (2-minute TTL) and `with_cap()` (response size limit).
Error responses always include an `"error"` key so the agent can handle failures gracefully.

---

## CloudWatch

### `get_alarms(state?)`
List CloudWatch alarms, optionally filtered by state.

| Param | Type | Default | Description |
|---|---|---|---|
| `state` | `string` | none | Filter: `OK`, `ALARM`, or `INSUFFICIENT_DATA` |

**Returns:** `{ alarms: [{name, state, reason, metric, namespace, updated_at}], count }`

---

### `get_alarm_history(alarm_name, hours?)`
Fetch state-change history for a specific alarm.

| Param | Type | Default | Description |
|---|---|---|---|
| `alarm_name` | `string` | required | CloudWatch alarm name |
| `hours` | `int` | `24` | How far back to look |

**Returns:** `{ alarm_name, history: [{timestamp, summary}], count }`

---

### `get_metric_data(namespace, metric, dimensions, period?, hours?, stat?)`
Fetch raw CloudWatch metric datapoints.

| Param | Type | Default | Description |
|---|---|---|---|
| `namespace` | `string` | required | e.g. `AWS/Lambda` |
| `metric` | `string` | required | e.g. `Errors` |
| `dimensions` | `list` | required | e.g. `[{"Name": "FunctionName", "Value": "my-fn"}]` |
| `period` | `int` | `300` | Period in seconds |
| `hours` | `int` | `3` | How far back to look |
| `stat` | `string` | `Sum` | `Sum`, `Average`, or `Maximum` |

**Returns:** `{ namespace, metric, stat, datapoints: [{timestamp, value}], count }`

---

### `get_log_events(log_group, log_stream?, filter_pattern?, hours?, limit?)`
Fetch recent log events from a CloudWatch Logs group.

| Param | Type | Default | Description |
|---|---|---|---|
| `log_group` | `string` | required | CloudWatch log group name |
| `log_stream` | `string` | none | Specific stream to read |
| `filter_pattern` | `string` | none | CloudWatch filter pattern, e.g. `ERROR` |
| `hours` | `int` | `1` | How far back to look |
| `limit` | `int` | `100` | Max events to return |

**Returns:** `{ log_group, events: [{timestamp, message, stream}], count }`

> **Tip:** Always call `describe_log_groups` first to discover the real log group name — never guess it.

---

### `describe_log_groups(prefix?)`
List CloudWatch log groups, optionally filtered by name prefix.

| Param | Type | Default | Description |
|---|---|---|---|
| `prefix` | `string` | none | Filter by log group name prefix |

**Returns:** `{ log_groups: [{name, retention_days, stored_bytes}], count }`

---

### `query_logs_insights(log_group, query, hours?, limit?)`
Run a CloudWatch Logs Insights structured query. Supports the full query language:
`fields`, `filter`, `stats`, `sort`, `limit`.

| Param | Type | Default | Description |
|---|---|---|---|
| `log_group` | `string` | required | Log group name (e.g. `/aws/lambda/my-fn`) |
| `query` | `string` | required | Logs Insights query string |
| `hours` | `int` | `1` | Time window to search |
| `limit` | `int` | `100` | Max results |

**Returns:** `{ log_group, query, results: [{}], count, scanned_mb }`

Example queries:
```
fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 50
stats count(*) as errors by bin(5m) | sort errors desc
```

---

## CloudTrail

### `lookup_cloudtrail_events(hours?, resource_name?, event_name?, limit?)`
Look up recent API events to find deployments, config changes, and permission changes.

| Param | Type | Default | Description |
|---|---|---|---|
| `hours` | `int` | `2` | How far back to look |
| `resource_name` | `string` | none | Filter by resource name (e.g. Lambda function name) |
| `event_name` | `string` | none | Filter by API event (e.g. `UpdateFunctionCode`) |
| `limit` | `int` | `50` | Max events (capped at 50 by AWS) |

**Returns:** `{ events: [{event_name, event_time, username, resources, event_id}], count }`

Common events to look for: `UpdateFunctionCode`, `UpdateFunctionConfiguration`,
`PutFunctionConcurrency`, `CreateDeployment`, `UpdateService`.

---

## ECS

> **Note:** Always call `list_ecs_clusters` first to discover real cluster names — never guess them.

### `list_ecs_clusters()`
List all ECS clusters in the region with status and task counts.

**Returns:** `{ clusters: [{name, arn, status, active_services, running_tasks, pending_tasks}], count }`

---

### `list_ecs_services(cluster)`
List services in a cluster with their desired/running/pending task counts.

| Param | Type | Description |
|---|---|---|
| `cluster` | `string` | Cluster name or ARN |

**Returns:** `{ cluster, services: [{name, status, desired, running, pending, task_definition}], count }`

---

### `describe_ecs_service(cluster, service)`
Get detailed info about an ECS service including recent events and deployments.

| Param | Type | Description |
|---|---|---|
| `cluster` | `string` | Cluster name or ARN |
| `service` | `string` | Service name or ARN |

**Returns:** `{ name, status, desired, running, pending, deployments: [{status, desired, running, failed, created_at, task_definition}], events: [{created_at, message}] }`

---

### `get_ecs_task_logs(cluster, task_id, log_group, limit?)`
Fetch stdout/stderr logs for a specific ECS task from CloudWatch Logs.

| Param | Type | Default | Description |
|---|---|---|---|
| `cluster` | `string` | required | Cluster name |
| `task_id` | `string` | required | Task ID (short or full ARN) |
| `log_group` | `string` | required | CloudWatch log group, often `/ecs/<service-name>` |
| `limit` | `int` | `100` | Max log lines |

**Returns:** `{ task_id, log_group, events: [{message}], count }`

---

## Lambda

### `list_lambda_functions()`
List all Lambda functions in the region.

**Returns:** `{ functions: [{name, runtime, memory_mb, timeout_s, last_modified}], count }`

---

### `get_lambda_function_config(name)`
Get detailed configuration for a Lambda function.

| Param | Type | Description |
|---|---|---|
| `name` | `string` | Lambda function name |

**Returns:** `{ name, runtime, memory_mb, timeout_s, last_modified, env_var_keys, layers, vpc_enabled, reserved_concurrency }`

> `reserved_concurrency: 0` means the function is fully throttled (intentional or misconfiguration).

---

### `get_lambda_error_rate(name, hours?)`
Get error count, throttle count, and invocation count from CloudWatch.

| Param | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | required | Lambda function name |
| `hours` | `int` | `3` | How far back to look |

**Returns:** `{ function, hours, total_invocations, total_errors, total_throttles, error_rate_pct, errors_by_period, throttles_by_period }`

---

## EC2

### `describe_ec2_instances(filters?)`
List EC2 instances with state, type, and tags.

| Param | Type | Default | Description |
|---|---|---|---|
| `filters` | `list` | none | EC2 filters, e.g. `[{"Name": "instance-state-name", "Values": ["running"]}]` |

**Returns:** `{ instances: [{instance_id, name, type, state, az, private_ip, launch_time}], count }`

---

### `get_ec2_system_status(instance_id)`
Get EC2 instance status checks (system reachability and instance reachability).

| Param | Type | Description |
|---|---|---|
| `instance_id` | `string` | EC2 instance ID |

**Returns:** `{ instance_id, instance_state, system_status, instance_status, system_events }`

---

## RDS

### `describe_rds_instances()`
List RDS DB instances with status, engine, class, and multi-AZ configuration.

**Returns:** `{ instances: [{identifier, status, engine, class, multi_az, storage_gb, endpoint}], count }`

---

### `get_rds_events(hours?, db_identifier?)`
Fetch RDS events log for recent database activity, failovers, and maintenance.

| Param | Type | Default | Description |
|---|---|---|---|
| `hours` | `int` | `24` | How far back to look |
| `db_identifier` | `string` | none | Filter by specific DB instance identifier |

**Returns:** `{ events: [{source, message, date, categories}], count }`

---

## IAM / STS

### `get_caller_identity()`
Return the current AWS caller identity — confirms which account and role the agent is using.

**Returns:** `{ account_id, arn, user_id }`

---

### `get_iam_role_policies(role_name)`
List policies (attached and inline) on an IAM role.

| Param | Type | Description |
|---|---|---|
| `role_name` | `string` | IAM role name |

**Returns:** `{ role, attached_policies: [{name, arn}], inline_policy_names }`

---

## Bash Execution Tool

### `run_bash_command(command)`
Run a read-only shell command. Covers the full AWS CLI surface for services not
available via the structured boto3 tools (S3, DynamoDB, SNS, SQS, Route53, ACM,
Secrets Manager, SSM, etc.), plus kubectl and docker.

**Allowed commands:**
- `aws <service> <operation>` where operation starts with: `describe-*`, `list-*`, `get-*`, `lookup-*`, `filter-*`, `search-*`, `scan-*`, `query*`, `batch-get-*`
- `kubectl get / describe / logs`
- `docker ps / logs / inspect`

**Rules:** No chaining (`&&`, `|`, `;`), no state-modifying commands. Max command length: 2000 chars. Hard timeout: 30s. Output capped at 4000 chars.

**Returns:** `{ success, output, error, command, blocked }`

If `blocked: true` the command was rejected by the allowlist — do not retry with a variation.

---

## History Tools

### `get_investigation_history(days?)`
Cross-session analytics: top alarms investigated, top Lambda functions, recurring
tool errors, and daily investigation frequency. Data is aggregated at the DB level —
no raw message content is read.

| Param | Type | Default | Description |
|---|---|---|---|
| `days` | `int` | `30` | How many days to look back |

**Returns:** `{ days, top_alarms, top_lambdas, recurring_errors, trend }`

---

### `search_past_investigations(query, limit?)`
Search past session titles and messages by keyword. Returns session summaries with
short snippets — never full message bodies.

| Param | Type | Default | Description |
|---|---|---|---|
| `query` | `string` | required | Keyword or phrase (e.g. alarm name, service, error type) |
| `limit` | `int` | `10` | Max results (capped at 20) |

**Returns:** `{ results: [{id, title, last_active_at, model, snippet}], count }`
