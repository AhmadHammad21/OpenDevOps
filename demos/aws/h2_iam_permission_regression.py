"""
H2 — IAM permission regression ("what changed" across IAM + CloudTrail).

A Lambda lists an S3 bucket. Its execution role starts WITH S3 read access, runs
clean, then we DETACH the S3 policy (DetachRolePolicy). Now every invocation
fails with AccessDenied — and the cause is a permission change, not the code.

Ask the agent:  "opendevops-demo-reader suddenly gets AccessDenied, what changed?"
Expect: get_log_events (AccessDenied) + get_iam_role_policies (S3 policy gone)
+ lookup_cloudtrail_events (DetachRolePolicy). CloudTrail may lag 5-15 min.

  uv run python demos/h2_iam_permission_regression.py setup
  uv run python demos/h2_iam_permission_regression.py teardown
"""

from __future__ import annotations

import time

import _common as c
from botocore.exceptions import ClientError

FN = f"{c.PREFIX}-reader"
ROLE = f"{c.PREFIX}-reader-role"
BASIC = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
S3_READ = "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"


def _bucket_name(sess: c.boto3.Session) -> str:
    acct = sess.client("sts").get_caller_identity()["Account"]
    return f"{c.PREFIX}-{acct}-bucket"


def _code(bucket: str) -> str:
    return f"""
import boto3
s3 = boto3.client("s3")
def handler(event, context):
    resp = s3.list_objects_v2(Bucket="{bucket}")     # needs s3:ListBucket
    return {{"key_count": resp.get("KeyCount", 0)}}
"""


def setup() -> None:
    sess = c.session()
    c.whoami(sess)
    bucket = _bucket_name(sess)
    s3 = sess.client("s3")
    try:
        if c.REGION == "us-east-1":
            s3.create_bucket(Bucket=bucket)
        else:
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": c.REGION},
            )
        c.log(f"created bucket {bucket}")
    except ClientError as e:
        if e.response["Error"]["Code"] not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            raise
        c.log(f"bucket {bucket} already exists")

    role = c.ensure_role(sess, ROLE, [BASIC, S3_READ])
    c.create_lambda(sess, FN, _code(bucket), role)
    c.log("clean run WITH permissions:")
    c.invoke_n(sess, FN, n=3)

    sess.client("iam").detach_role_policy(RoleName=ROLE, PolicyArn=S3_READ)
    c.log("DETACHED S3 read policy (the regression). Waiting 15s to propagate...")
    time.sleep(15)
    c.invoke_n(sess, FN, n=6)
    c.log("DONE. Investigate: 'opendevops-demo-reader gets AccessDenied, what changed?'")


def teardown() -> None:
    sess = c.session()
    c.delete_lambda(sess, FN)
    c.delete_role(sess, ROLE)
    bucket = _bucket_name(sess)
    s3 = sess.client("s3")
    try:
        objs = s3.list_objects_v2(Bucket=bucket).get("Contents", [])
        for o in objs:
            s3.delete_object(Bucket=bucket, Key=o["Key"])
        s3.delete_bucket(Bucket=bucket)
        c.log(f"deleted bucket {bucket}")
    except ClientError as e:
        if e.response["Error"]["Code"] not in ("NoSuchBucket", "404"):
            c.log(f"bucket delete skipped: {e.response['Error']['Code']}")


if __name__ == "__main__":
    action = c.parse_action(__doc__)
    setup() if action == "setup" else teardown()
