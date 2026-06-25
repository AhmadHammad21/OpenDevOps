# Tool & Permission Inventory

> **Generated file — do not edit by hand.** Produced by `apps/backend/scripts/gen_tool_inventory.py` from the live code (`opendevops_core.agent.inventory.build_inventory`), the same source that backs the read-only `GET /api/inventory` endpoint. Regenerate with `cd apps/backend && uv run python scripts/gen_tool_inventory.py`.

This is the trust artifact: exactly what the agent can inspect — every registered tool and its parameters, the read-only bash command allowlist, the AWS read-permission probe, and the per-cloud capability tiers. Everything is read-only.

## Capability by cloud

| Cloud | Structured SDK tools | CLI access (`bash` tool) | Event-driven + polling |
|---|---|---|---|
| **AWS** (active) | 20 | yes | yes |
| **AZURE** | 0 | yes | no |
| **GCP** | 0 | no | no |

Active provider: **aws** · total registered tools: **26**.

## Registered tools

### `cloudwatch`

#### `get_alarms` → `dict`

List CloudWatch alarms, optionally filtered by state (OK, ALARM, INSUFFICIENT_DATA).

| Param | Type | Default |
|---|---|---|
| `state` | `str \| None` | `None` |

#### `get_alarm_history` → `dict`

Fetch state-change history for a specific CloudWatch alarm.

| Param | Type | Default |
|---|---|---|
| `alarm_name` | `str` | required |
| `hours` | `int` | `24` |

#### `get_metric_data` → `dict`

Fetch raw CloudWatch metric data points for a given namespace/metric/dimensions.

| Param | Type | Default |
|---|---|---|
| `namespace` | `str` | required |
| `metric` | `str` | required |
| `dimensions` | `list[dict[str, str]]` | required |
| `period` | `int` | `300` |
| `hours` | `int` | `3` |
| `stat` | `str` | `'Sum'` |

#### `get_log_events` → `dict`

Fetch recent log events from a CloudWatch Logs group, with optional filter pattern.

| Param | Type | Default |
|---|---|---|
| `log_group` | `str` | required |
| `log_stream` | `str \| None` | `None` |
| `filter_pattern` | `str \| None` | `None` |
| `hours` | `int` | `1` |
| `limit` | `int` | `100` |

#### `describe_log_groups` → `dict`

List CloudWatch log groups, optionally filtered by name prefix.

| Param | Type | Default |
|---|---|---|
| `prefix` | `str \| None` | `None` |

#### `query_logs_insights` → `dict`

Run a CloudWatch Logs Insights structured query against a log group.

| Param | Type | Default |
|---|---|---|
| `log_group` | `str` | required |
| `query` | `str` | required |
| `hours` | `int` | `1` |
| `limit` | `int` | `100` |

### `cloudtrail`

#### `lookup_cloudtrail_events` → `dict`

Look up recent CloudTrail API events.

| Param | Type | Default |
|---|---|---|
| `hours` | `int` | `2` |
| `resource_name` | `str \| None` | `None` |
| `event_name` | `str \| None` | `None` |
| `limit` | `int` | `50` |

### `ecs`

#### `list_ecs_clusters` → `dict`

List all ECS clusters in the region with their status and active service/task counts.

*No parameters.*

#### `list_ecs_services` → `dict`

List ECS services in a cluster with their desired, running, and pending task counts.

| Param | Type | Default |
|---|---|---|
| `cluster` | `str` | required |

#### `describe_ecs_service` → `dict`

Get detailed info about an ECS service including recent events and deployment status.

| Param | Type | Default |
|---|---|---|
| `cluster` | `str` | required |
| `service` | `str` | required |

#### `get_ecs_task_logs` → `dict`

Fetch stdout/stderr logs for a specific ECS task from CloudWatch Logs.

| Param | Type | Default |
|---|---|---|
| `cluster` | `str` | required |
| `task_id` | `str` | required |
| `log_group` | `str` | required |
| `limit` | `int` | `100` |

### `lambda_`

#### `list_lambda_functions` → `dict`

List all Lambda functions in the region with their runtime, memory, and timeout.

*No parameters.*

#### `get_lambda_function_config` → `dict`

Get detailed configuration for a Lambda function: memory, timeout, env vars, layers, VPC.

| Param | Type | Default |
|---|---|---|
| `name` | `str` | required |

#### `get_lambda_error_rate` → `dict`

Get Lambda error count and throttle count from CloudWatch for a given time window.

| Param | Type | Default |
|---|---|---|
| `name` | `str` | required |
| `hours` | `int` | `3` |

### `ec2`

#### `describe_ec2_instances` → `dict`

List EC2 instances with their state, type, and tags. Optionally filter by state or tag.

| Param | Type | Default |
|---|---|---|
| `filters` | `list[dict[str, Any]] \| None` | `None` |

#### `get_ec2_system_status` → `dict`

Get EC2 instance status checks (system reachability and instance reachability).

| Param | Type | Default |
|---|---|---|
| `instance_id` | `str` | required |

### `rds`

#### `describe_rds_instances` → `dict`

List RDS DB instances with their status, engine, class, and multi-AZ configuration.

*No parameters.*

#### `get_rds_events` → `dict`

Fetch RDS events log for recent database activity, failovers, maintenance, and errors.

| Param | Type | Default |
|---|---|---|
| `hours` | `int` | `24` |
| `db_identifier` | `str \| None` | `None` |

### `iam`

#### `get_caller_identity` → `dict`

Return the current AWS caller identity: account ID, user/role ARN, and user ID.

*No parameters.*

#### `get_iam_role_policies` → `dict`

List policies attached to an IAM role.

| Param | Type | Default |
|---|---|---|
| `role_name` | `str` | required |

### `history`

#### `get_investigation_history` → `dict`

Get cross-session investigation analytics: top alarms investigated, top Lambda functions, recurring tool errors, and daily investigation frequency over the last N days. Never loads raw message content — all data is aggregated at the DB level.

| Param | Type | Default |
|---|---|---|
| `days` | `int` | `30` |

#### `search_past_investigations` → `dict`

Search past investigation sessions by keyword in title or message content. Returns session summaries with a short snippet — never full message bodies.

| Param | Type | Default |
|---|---|---|
| `query` | `str` | required |
| `limit` | `int` | `10` |

### `bash_tool`

#### `run_bash_command` → `dict[str, Any]`

Run a read-only shell command and return structured output.

| Param | Type | Default |
|---|---|---|
| `command` | `str` | required |

### `skills`

#### `list_skills` → `dict`

List all available investigation skills with their names and descriptions.

*No parameters.*

#### `use_skill` → `dict`

Load the full investigation skill for a named incident type. The skill contains step-by-step investigation guidance, key metrics to check, log patterns to look for, and common root causes with mitigations.

| Param | Type | Default |
|---|---|---|
| `name` | `str` | required |

### `final_answer`

#### `submit_investigation` → `str`

Submit the final structured investigation result. Call this exactly once when you have gathered sufficient evidence and reached a conclusion. Do not output a JSON block in free text — call this tool instead.

| Param | Type | Default |
|---|---|---|
| `root_cause_category` | `Literal['SYSTEM_CHANGE', 'INPUT_ANOMALY', 'RESOURCE_LIMIT', 'COMPONENT_FAILURE', 'DEPENDENCY_ISSUE', 'UNKNOWN']` | required |
| `root_cause_summary` | `str` | required |
| `evidence` | `list[str]` | required |
| `mitigation_steps` | `list[str]` | required |
| `validation_steps` | `list[str]` | required |
| `confidence` | `Literal['HIGH', 'MEDIUM', 'LOW']` | required |
| `services_affected` | `list[str]` | required |
| `recommended_follow_up` | `str` | required |
| `follow_up_questions` | `list[str]` | required |

## Bash command allowlist

`run_bash_command` runs only read-only commands, validated against this allowlist before execution. Shell chaining is **blocked**, `shell=True` is never used, output is capped at 4000 chars, and every command has a hard 30s timeout.

- **aws** — aws <service> <operation> where the operation starts with a read-only verb. Read-only verbs: `batch-get`, `check`, `describe`, `filter`, `get`, `list`, `lookup`, `query`, `scan`, `search`, `show`, `view`. Blocked global flags: `--endpoint-url`.
- **az** — az <group...> <verb> where the trailing verb is read-only. Read-only verbs: `check`, `describe`, `get`, `list`, `query`, `show`, `tail`, `version`.
- **kubectl** — subcommands: `describe`, `get`, `logs`.
- **docker** — subcommands: `inspect`, `logs`, `ps`.

## AWS read-permission matrix

One lightweight read call per service verifies the agent's credentials (surfaced by the in-app permission checker).

| Service | boto3 client | Read operation |
|---|---|---|
| cloudwatch | `cloudwatch` | `describe_alarms` |
| cloudtrail | `cloudtrail` | `lookup_events` |
| ecs | `ecs` | `list_clusters` |
| lambda | `lambda` | `list_functions` |
| ec2 | `ec2` | `describe_instances` |
| rds | `rds` | `describe_db_instances` |
| iam | `sts` | `get_caller_identity` |
| sqs | `sqs` | `list_queues` |
| events | `events` | `list_rules` |
