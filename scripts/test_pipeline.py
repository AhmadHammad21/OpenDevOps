#!/usr/bin/env python3
"""
test_pipeline.py — trigger a real Lambda failure through the monitoring pipeline.

No IAM role creation needed — picks an existing Lambda from your account,
invokes it with a bad payload to generate real CloudWatch Logs errors,
then pushes an alarm event to SQS so the agent investigates.

Usage:
  uv run python scripts/test_pipeline.py                         # auto-pick a Lambda
  uv run python scripts/test_pipeline.py --function my-function  # use specific Lambda
  uv run python scripts/test_pipeline.py --region eu-west-1
  uv run python scripts/test_pipeline.py --invocations 10
  uv run python scripts/test_pipeline.py --list                  # list available Lambdas
  uv run python scripts/test_pipeline.py --lambda-only           # real alarm path (~2-4 min)

─────────────────────────────────────────────────────────────────────────────────
MANUAL SQS TEST COMMANDS (bypass script — push directly to the queue)
Replace QUEUE_URL and ACCOUNT_ID with your values from Settings → AWS Configuration.
─────────────────────────────────────────────────────────────────────────────────

# Syntax error (Runtime.UserCodeSyntaxError) — fast, focused investigation:
aws sqs send-message --profile devops-agent-readonly --queue-url "https://sqs.us-east-1.amazonaws.com/ACCOUNT_ID/opendevops-agent-events" --message-body "{\"source\":\"aws.lambda\",\"detail-type\":\"Lambda Function Invocation Result - Failure\",\"time\":\"2026-05-17T12:00:00Z\",\"detail\":{\"requestContext\":{\"functionArn\":\"arn:aws:lambda:us-east-1:ACCOUNT_ID:function:opendevops-test-failure\",\"condition\":\"RetriesExhausted\",\"approximateInvokeCount\":3},\"responsePayload\":{\"errorMessage\":\"Syntax error in module lambda_function: unexpected indent (lambda_function.py, line 9)\",\"errorType\":\"Runtime.UserCodeSyntaxError\",\"stackTrace\":[\"File /var/task/lambda_function.py line 9: def lambda_handler(event, context):\"]}}}

# CloudWatch alarm event — slower path (~1 min CloudWatch delay in real scenario):
aws sqs send-message --profile devops-agent-readonly \
  --queue-url "https://sqs.us-east-1.amazonaws.com/ACCOUNT_ID/opendevops-agent-events" \
  --message-body "{\"source\":\"aws.cloudwatch\",\"detail-type\":\"CloudWatch Alarm State Change\",\"time\":\"2026-05-17T12:00:00Z\",\"detail\":{\"alarmName\":\"opendevops-test-lambda-errors\",\"state\":{\"value\":\"ALARM\",\"reason\":\"TEST: Lambda error rate exceeded threshold\"},\"configuration\":{\"metrics\":[{\"metricStat\":{\"metric\":{\"namespace\":\"AWS/Lambda\",\"name\":\"Errors\",\"dimensions\":{\"FunctionName\":\"opendevops-test-failure\"}},\"period\":300,\"stat\":\"Sum\"}}]}}}"

Notes:
  - Event consumer picks up the message within 20s (SQS long-poll interval)
  - Use aws.lambda source for faster, more focused investigations
  - MAX_TOOL_CALLS=30 recommended to avoid recursion errors with weaker models
─────────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sqlite3
import sys

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

load_dotenv()

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"


def log(msg: str) -> None:
    print(f"{GREEN}[+]{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[!]{NC} {msg}")


def die(msg: str) -> None:
    print(f"{RED}[✗]{NC} {msg}", file=sys.stderr)
    sys.exit(1)


def get_queue_url() -> str:
    if queue_url := os.environ.get("SQS_QUEUE_URL", ""):
        return queue_url

    sqlite_path = os.environ.get("SQLITE_PATH", "./data/agent.db")
    if os.path.exists(sqlite_path):
        try:
            with sqlite3.connect(sqlite_path) as conn:
                row = conn.execute(
                    "SELECT value FROM app_config WHERE key = 'init'"
                ).fetchone()
            if row:
                return json.loads(row[0]).get("sqs_queue_url", "")
        except Exception:
            pass
    return ""


def list_functions(lam) -> list[str]:
    names: list[str] = []
    paginator = lam.get_paginator("list_functions")
    for page in paginator.paginate():
        for fn in page.get("Functions", []):
            names.append(fn["FunctionName"])
    return sorted(names)


def run(
    region: str,
    invocations: int,
    function_name: str | None,
    list_only: bool,
    lambda_only: bool = False,
) -> None:
    try:
        session = boto3.Session()
        lam = session.client("lambda", region_name=region)
        sqs = session.client("sqs", region_name=region)
        cw = session.client("cloudwatch", region_name=region)
    except NoCredentialsError:
        die("No AWS credentials found. Configure via environment variables or ~/.aws/credentials.")

    # ── credential check ──────────────────────────────────────────────────────
    try:
        sts = session.client("sts", region_name=region)
        identity = sts.get_caller_identity()
        log(f"AWS identity: {identity.get('Arn', 'unknown')}")
    except ClientError as e:
        die(
            f"AWS credentials error: {e}\n"
            "Run 'aws sso login' or set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY."
        )

    # ── list mode ─────────────────────────────────────────────────────────────
    functions = list_functions(lam)
    if list_only:
        if not functions:
            warn("No Lambda functions found in this account/region.")
        else:
            print(f"\nAvailable Lambda functions in {region}:")
            for fn in functions:
                print(f"  {fn}")
        return

    # ── pick Lambda ───────────────────────────────────────────────────────────
    if function_name:
        # verify it exists
        try:
            lam.get_function(FunctionName=function_name)
        except ClientError:
            die(f"Lambda function '{function_name}' not found in {region}.")
    else:
        if not functions:
            die(f"No Lambda functions found in {region}. Use --function to specify one.")
        function_name = functions[0]
        log(f"Auto-selected Lambda: {function_name}  (use --list to see all, --function to pick)")

    queue_url = get_queue_url()
    if not queue_url:
        die(
            "No SQS queue URL found. Run 'Create Infrastructure' in Settings first."
        )

    log(f"Region    : {region}")
    log(f"Queue     : {queue_url}")
    log(f"Function  : {function_name}")
    print()

    # ── invoke Lambda with intentionally bad payload ──────────────────────────
    log(f"Invoking '{function_name}' {invocations}× with a bad payload to generate real errors...")
    bad_payload = b'{"__test_force_error": true, "trigger": "opendevops-pipeline-test"}'
    succeeded = 0
    errors_observed = 0
    for i in range(1, invocations + 1):
        try:
            resp = lam.invoke(
                FunctionName=function_name,
                InvocationType="RequestResponse",
                Payload=bad_payload,
            )
            status = resp.get("StatusCode", 0)
            fn_error = resp.get("FunctionError", "")
            if fn_error or status >= 400:
                print(f"  invocation {i}/{invocations}  → error (good)")
                errors_observed += 1
            else:
                print(
                    f"  invocation {i}/{invocations}  → success "
                    "(function handled bad input gracefully)"
                )
            succeeded += 1
        except ClientError as e:
            warn(f"  invocation {i}/{invocations}  → invoke failed: {e}")

    if succeeded == 0:
        warn("All invocations failed to reach the function — no logs may exist.")
    elif errors_observed == 0:
        warn(
            "The function handled the test payload successfully — Lambda Errors may stay at 0."
        )
    else:
        log(f"Real invocation logs at: CloudWatch → /aws/lambda/{function_name}")
    print()

    # ── lambda-only: skip manual SQS push, let alarm fire naturally ──────────
    if lambda_only:
        if errors_observed == 0:
            die(
                "No Lambda function errors were observed; the alarm is unlikely to fire."
            )
        try:
            alarm = cw.describe_alarms(AlarmNames=["opendevops-lambda-errors-aggregate"]).get(
                "MetricAlarms", []
            )
            if alarm and alarm[0].get("StateValue") == "ALARM":
                warn(
                    "Aggregate alarm is already in ALARM; EventBridge may not emit a transition."
                )
        except ClientError as e:
            warn(f"Could not inspect aggregate alarm state: {e}")

        sep = "━" * 60
        print(f"\n{GREEN}{sep}{NC}")
        print(f"{GREEN}✓ Lambda invoked — waiting for alarm to fire automatically{NC}")
        print(f"  Function  : {function_name}")
        print("  Alarm     : opendevops-lambda-errors-aggregate")
        print(f"  Real logs : CloudWatch → /aws/lambda/{function_name}")
        print("  Monitoring: http://localhost/monitoring")
        print(f"{GREEN}{sep}{NC}\n")
        warn("CloudWatch evaluates every 60s — alarm should trip in ~1-2 minutes.")
        warn("EventBridge fires → SQS → agent investigates automatically.")
        warn("Watch server logs for: 'Processing event: aws.cloudwatch'")
        return

    # ── push alarm event to SQS ───────────────────────────────────────────────
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    event = {
        "source": "aws.cloudwatch",
        "detail-type": "CloudWatch Alarm State Change",
        "time": now,
        "region": region,
        "detail": {
            "alarmName": f"{function_name}-test-errors",
            "state": {
                "value": "ALARM",
                "reason": (
                    f"Threshold Crossed: {invocations} error datapoints"
                    " in the last 1 minute (threshold: 1). Triggered by pipeline test."
                ),
            },
            "configuration": {
                "metrics": [
                    {
                        "metricStat": {
                            "metric": {
                                "namespace": "AWS/Lambda",
                                "name": "Errors",
                                "dimensions": {"FunctionName": function_name},
                            },
                            "period": 60,
                            "stat": "Sum",
                        },
                    }
                ],
            },
        },
    }

    log("Sending alarm event to SQS manually (bypasses EventBridge)...")
    try:
        msg_id = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(event),
        )["MessageId"]
    except ClientError as e:
        die(f"Failed to send SQS message: {e}")

    sep = "━" * 60
    print(f"\n{GREEN}{sep}{NC}")
    print(f"{GREEN}✓ Pipeline triggered (manual SQS push){NC}")
    print(f"  MessageId : {msg_id}")
    print(f"  Function  : {function_name}")
    print(f"  Real logs : CloudWatch → /aws/lambda/{function_name}")
    print("  Monitoring: http://localhost/monitoring")
    print(f"{GREEN}{sep}{NC}\n")
    warn("The agent will pull REAL CloudWatch logs from that function.")
    warn("Investigation takes ~30–90s. Watch the Monitoring page.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Trigger a real Lambda failure through the monitoring pipeline"
    )
    parser.add_argument(
        "--function", help="Lambda function name to use (auto-picks first if omitted)"
    )
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    parser.add_argument("--invocations", type=int, default=5)
    parser.add_argument(
        "--list", action="store_true", help="List available Lambda functions and exit"
    )
    parser.add_argument(
        "--lambda-only",
        action="store_true",
        dest="lambda_only",
        help="Invoke Lambda and let the CloudWatch alarm fire automatically",
    )
    args = parser.parse_args()
    run(args.region, args.invocations, args.function, args.list, args.lambda_only)


if __name__ == "__main__":
    main()
