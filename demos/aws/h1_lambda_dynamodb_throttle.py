"""
H1 — Lambda errors caused by DynamoDB throttling (cross-service root cause).

Creates a DynamoDB table provisioned at 1 WCU, plus a Lambda that fires 800
concurrent ~2KB writes at it with SDK retries disabled — enough to drain the
table's burst capacity so DynamoDB raises ProvisionedThroughputExceededException
instead of silently retrying it away. The Lambda errors are only a SYMPTOM — the
real cause is the table's capacity. The agent has to read the Lambda logs, spot
the Dynamo exception, then use the bash tool (`aws dynamodb describe-table`) to
confirm the 1 WCU ceiling is the bottleneck.

The function errors reliably, so the poller will also auto-investigate it on its
next tick (error rate is ~100%, well over the 5% threshold).

Ask the agent:  "opendevops-demo-writer is throwing errors, find the root cause"
Expect: get_log_events (ProvisionedThroughputExceeded) + run_bash_command
(aws dynamodb describe-table) for provisioned capacity.

  uv run python demos/h1_lambda_dynamodb_throttle.py setup
  uv run python demos/h1_lambda_dynamodb_throttle.py teardown
"""

from __future__ import annotations

import time

import _common as c
from botocore.exceptions import ClientError

FN = f"{c.PREFIX}-writer"
TABLE = f"{c.PREFIX}-orders"
ROLE = f"{c.PREFIX}-dynamo-role"
BASIC = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
DYNAMO = "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"

CODE = """
import os
import boto3
from botocore.config import Config
from concurrent.futures import ThreadPoolExecutor

# max_attempts=1 => boto3 does NOT silently retry throttles; they surface at once.
ddb = boto3.client("dynamodb", config=Config(retries={"max_attempts": 1}))
TABLE = os.environ["TABLE_NAME"]


def _put(i):
    ddb.put_item(
        TableName=TABLE,
        Item={
            "order_id": {"S": f"order-{i}"},
            "amount": {"N": "100"},
            "payload": {"S": "x" * 2000},   # ~2 WCU per write, drains burst faster
        },
    )


def handler(event, context):
    # 800 concurrent ~2KB writes against a 1 WCU table exhausts burst capacity, so
    # DynamoDB raises ProvisionedThroughputExceededException, which propagates here.
    with ThreadPoolExecutor(max_workers=25) as pool:
        list(pool.map(_put, range(800)))
    return {"written": 800}
"""


def setup() -> None:
    sess = c.session()
    c.whoami(sess)
    ddb = sess.client("dynamodb")
    try:
        ddb.create_table(
            TableName=TABLE,
            AttributeDefinitions=[{"AttributeName": "order_id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "order_id", "KeyType": "HASH"}],
            BillingMode="PROVISIONED",
            ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        )
        ddb.get_waiter("table_exists").wait(TableName=TABLE)
        c.log(f"created table {TABLE} at 1 RCU / 1 WCU")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceInUseException":
            raise
        c.log(f"table {TABLE} already exists")

    role = c.ensure_role(sess, ROLE, [BASIC, DYNAMO])
    c.create_lambda(sess, FN, CODE, role, timeout=30, env={"TABLE_NAME": TABLE})
    time.sleep(3)
    c.invoke_n(sess, FN, n=4)
    c.log("DONE. Investigate: 'opendevops-demo-writer is erroring, root cause?'")


def teardown() -> None:
    sess = c.session()
    c.delete_lambda(sess, FN)
    c.delete_role(sess, ROLE)
    try:
        sess.client("dynamodb").delete_table(TableName=TABLE)
        c.log(f"deleted table {TABLE}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise


if __name__ == "__main__":
    action = c.parse_action(__doc__)
    setup() if action == "setup" else teardown()
