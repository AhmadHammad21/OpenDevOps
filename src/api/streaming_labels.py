"""Contextual loading copy shown in the UI while tool calls are in flight."""

from __future__ import annotations

# Keys match tool function names exactly. "default" is the fallback for
# unknown tools; "reasoning" is used before the first tool call fires.
STREAMING_LABELS: dict[str, list[str]] = {
    # ── CloudWatch ────────────────────────────────────────────────────────────
    "get_alarms": [
        "Interrogating your alarms…",
        "Scanning for ALARM state…",
        "Checking what's on fire…",
        "Reviewing alarm health…",
    ],
    "get_alarm_history": [
        "Rewinding the alarm timeline…",
        "Digging through alarm state changes…",
        "Tracing when things went sideways…",
        "Inspecting the alarm changelog…",
    ],
    "get_metric_data": [
        "Squinting at the metric curves…",
        "Lemonizing metrics…",
        "Charting the spikes…",
        "Pulling raw metric data…",
        "Plotting the telemetry…",
    ],
    "get_log_events": [
        "Tailing the logs…",
        "Reading between the log lines…",
        "Sifting through log events…",
        "Following the log trail…",
    ],
    "describe_log_groups": [
        "Mapping the log landscape…",
        "Cataloguing log groups…",
        "Discovering available log streams…",
        "Surveying what's being logged…",
    ],
    "query_logs_insights": [
        "Running a Logs Insights query…",
        "Combing through log patterns…",
        "Firing up the query engine…",
        "Mining logs for signals…",
        "Asking CloudWatch the hard questions…",
    ],

    # ── CloudTrail ────────────────────────────────────────────────────────────
    "lookup_cloudtrail_events": [
        "Digging through CloudTrail…",
        "Retracing recent API footsteps…",
        "Hunting for who changed what…",
        "Backtracking through the audit trail…",
        "Following the API breadcrumbs…",
        "Checking recent deployments and config changes…",
    ],

    # ── ECS ───────────────────────────────────────────────────────────────────
    "list_ecs_clusters": [
        "Discovering ECS clusters…",
        "Mapping the cluster landscape…",
        "Rounding up clusters…",
        "Finding where your services live…",
    ],
    "list_ecs_services": [
        "Polling the cluster…",
        "Taking a head count in ECS…",
        "Rounding up the services…",
        "Checking cluster membership…",
    ],
    "describe_ecs_service": [
        "Counting heads in the cluster…",
        "Checking container vitals…",
        "Inspecting desired vs. running counts…",
        "Poking around the ECS service…",
        "Reviewing recent service events…",
    ],
    "get_ecs_task_logs": [
        "Fetching task stdout…",
        "Reading what the container said…",
        "Piping container logs…",
        "Grabbing task stderr too, just in case…",
    ],

    # ── Lambda ────────────────────────────────────────────────────────────────
    "list_lambda_functions": [
        "Cataloguing your Lambda fleet…",
        "Rounding up all the functions…",
        "Counting serverless units…",
        "Surveying the Lambda landscape…",
    ],
    "get_lambda_function_config": [
        "Reading Lambda config…",
        "Checking memory and timeout settings…",
        "Inspecting function environment variables…",
        "Reviewing function configuration…",
    ],
    "get_lambda_error_rate": [
        "Tallying Lambda grief…",
        "Counting serverless regrets…",
        "Measuring the error rate…",
        "Checking throttle and error counts…",
        "Asking CloudWatch how bad it really is…",
    ],

    # ── EC2 ───────────────────────────────────────────────────────────────────
    "describe_ec2_instances": [
        "Knocking on EC2's door…",
        "Checking on your instances…",
        "Running instance vitals…",
        "Surveying the fleet…",
    ],
    "get_ec2_system_status": [
        "Running system status checks…",
        "Checking if the instance can reach AWS…",
        "Verifying hardware health…",
        "Asking EC2 how it's feeling…",
    ],

    # ── RDS ───────────────────────────────────────────────────────────────────
    "describe_rds_instances": [
        "Checking in on your databases…",
        "Reviewing DB instance status…",
        "Inspecting the data layer…",
        "Peeking at RDS health…",
    ],
    "get_rds_events": [
        "Checking what the database has been up to…",
        "Scanning RDS event logs…",
        "Reviewing recent DB events…",
        "Following the database drama…",
    ],

    # ── IAM ───────────────────────────────────────────────────────────────────
    "get_caller_identity": [
        "Confirming AWS identity…",
        "Verifying who we are to AWS…",
        "Checking credentials…",
    ],
    "get_iam_role_policies": [
        "Reviewing IAM permissions…",
        "Checking who can do what…",
        "Auditing the role policies…",
        "Untangling IAM…",
    ],

    # ── Generic phases ────────────────────────────────────────────────────────
    "reasoning": [
        "Connecting the dots…",
        "Cooking up a root cause…",
        "Weighing the evidence…",
        "Triangulating the blast radius…",
        "Forming a hypothesis…",
        "Piecing the puzzle together…",
        "Thinking hard…",
        "Reviewing the crime scene…",
        "Drawing conclusions from the data…",
    ],
    "default": [
        "Poking around AWS…",
        "On the case…",
        "Gathering clues…",
        "Checking in with AWS…",
        "Running diagnostics…",
    ],
}
