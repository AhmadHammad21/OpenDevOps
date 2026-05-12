#!/usr/bin/env python3
"""
test_pipeline.py — create a real Lambda that errors, fire it through the monitoring pipeline.

Usage:
  uv run python scripts/test_pipeline.py                        # run test
  uv run python scripts/test_pipeline.py --region eu-west-1    # override region
  uv run python scripts/test_pipeline.py --invocations 10      # more errors
  uv run python scripts/test_pipeline.py --cleanup FUNCTION ROLE
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import sys
import time
import zipfile

import boto3
from botocore.exceptions import ClientError

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"


def log(msg: str)  -> None: print(f"{GREEN}[+]{NC} {msg}")
def warn(msg: str) -> None: print(f"{YELLOW}[!]{NC} {msg}")
def die(msg: str)  -> None: print(f"{RED}[✗]{NC} {msg}", file=sys.stderr); sys.exit(1)


LAMBDA_CODE = """\
import random

ERRORS = [
    "Connection pool exhausted: all 100 connections in use by active queries",
    "DynamoDB ProvisionedThroughputExceededException on table 'orders' — read capacity 0/500 RCU remaining",
    "Downstream service timeout: payments-service did not respond within 29000ms",
    "Redis READONLY error: connected to replica — write commands not accepted",
    "JWT verification failed: token expired 3601s ago (iat=1715000000)",
    "Unhandled exception: Cannot read property 'userId' of undefined at processOrder:47",
    "Out of memory: Lambda allocated 128 MB, peak usage 129 MB — increase memory limit",
]

def handler(event, context):
    error = random.choice(ERRORS)
    raise RuntimeError(f"[TEST FAILURE] {error}")
"""


def make_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.py", LAMBDA_CODE)
    return buf.getvalue()


def get_queue_url() -> str:
    init_path = os.path.join(os.path.dirname(__file__), "..", "data", "init.json")
    if os.path.exists(init_path):
        with open(init_path) as f:
            url = json.load(f).get("sqs_queue_url", "")
            if url:
                return url
    return os.environ.get("SQS_QUEUE_URL", "")


def cleanup(function_name: str, role_name: str, region: str) -> None:
    session = boto3.Session()
    lam = session.client("lambda", region_name=region)
    iam = session.client("iam")

    warn(f"Deleting Lambda: {function_name}")
    try:
        lam.delete_function(FunctionName=function_name)
        log("Lambda deleted")
    except ClientError:
        warn("Already gone")

    warn(f"Deleting IAM role: {role_name}")
    try:
        iam.detach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        )
    except ClientError:
        pass
    try:
        iam.delete_role(RoleName=role_name)
        log("Role deleted")
    except ClientError:
        warn("Already gone")

    log("Cleanup done.")


def run(region: str, invocations: int) -> None:
    queue_url = get_queue_url()
    if not queue_url:
        die("No SQS queue URL found. Run 'Create Infrastructure' in Settings → AWS Configuration first.")

    suffix = int(time.time())
    function_name = f"opendevops-test-error-{suffix}"
    role_name = f"opendevops-test-role-{suffix}"

    log(f"Region    : {region}")
    log(f"Queue     : {queue_url}")
    log(f"Function  : {function_name}")
    print()

    session = boto3.Session()
    iam = session.client("iam")
    lam = session.client("lambda", region_name=region)
    sqs = session.client("sqs", region_name=region)

    # ── create IAM role ──────────────────────────────────────────────────────
    log("Creating IAM execution role...")
    trust = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }],
    })
    role_arn = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=trust,
    )["Role"]["Arn"]
    iam.attach_role_policy(
        RoleName=role_name,
        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    )
    log(f"Role ARN  : {role_arn}")
    log("Waiting 10s for IAM role to propagate...")
    time.sleep(10)

    # ── deploy Lambda ────────────────────────────────────────────────────────
    log("Deploying Lambda function...")
    lam.create_function(
        FunctionName=function_name,
        Runtime="python3.12",
        Role=role_arn,
        Handler="index.handler",
        Code={"ZipFile": make_zip()},
        Timeout=10,
    )

    waiter = lam.get_waiter("function_active")
    waiter.wait(FunctionName=function_name)
    log("Lambda deployed.")

    # ── invoke to generate real errors + CloudWatch logs ────────────────────
    log(f"Invoking {invocations} times to generate real errors...")
    for i in range(1, invocations + 1):
        lam.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=b'{"test": true}',
        )
        print(f"  invocation {i}/{invocations}")

    log(f"Errors written to CloudWatch Logs: /aws/lambda/{function_name}")
    print()

    # ── push event to SQS with real function name ────────────────────────────
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    event = {
        "source": "aws.cloudwatch",
        "detail-type": "CloudWatch Alarm State Change",
        "time": now,
        "region": region,
        "detail": {
            "alarmName": f"{function_name}-errors",
            "state": {
                "value": "ALARM",
                "reason": (
                    f"Threshold Crossed: {invocations} error datapoints"
                    " in the last 1 minute (threshold: 1)."
                ),
            },
            "configuration": {
                "metrics": [{
                    "metricStat": {
                        "metric": {
                            "namespace": "AWS/Lambda",
                            "name": "Errors",
                            "dimensions": {"FunctionName": function_name},
                        },
                        "period": 60,
                        "stat": "Sum",
                    },
                }],
            },
        },
    }

    log("Sending event to SQS...")
    msg_id = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(event),
    )["MessageId"]

    sep = "━" * 60
    print(f"\n{GREEN}{sep}{NC}")
    print(f"{GREEN}✓ Pipeline triggered{NC}")
    print(f"  MessageId : {msg_id}")
    print(f"  Function  : {function_name}")
    print(f"  Real logs : CloudWatch → /aws/lambda/{function_name}")
    print(f"  Monitoring: http://localhost/monitoring")
    print(f"{GREEN}{sep}{NC}\n")
    warn("The agent will pull REAL CloudWatch logs from that function.")
    warn("Investigation takes ~30–90s. Watch the Monitoring page.")
    print(f"\nTo clean up when done:")
    print(f"  {YELLOW}uv run python scripts/test_pipeline.py --cleanup {function_name} {role_name}{NC}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fire a real Lambda failure through the monitoring pipeline")
    parser.add_argument("--cleanup", nargs=2, metavar=("FUNCTION", "ROLE"), help="Tear down resources")
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    parser.add_argument("--invocations", type=int, default=5)
    args = parser.parse_args()

    if args.cleanup:
        cleanup(args.cleanup[0], args.cleanup[1], args.region)
    else:
        run(args.region, args.invocations)


if __name__ == "__main__":
    main()
