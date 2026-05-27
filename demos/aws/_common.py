"""
Shared helpers for OpenDevOps demo scenarios.

Every scenario script imports from here. All resources are prefixed with
`opendevops-demo` so teardown can find them and you can spot them in the console.

Credentials come from the standard AWS chain. Override with:
  AWS_PROFILE=your-profile  AWS_REGION=us-east-1

These scripts CREATE REAL AWS RESOURCES (a few cents at most; ECS/RDS cost while
running). Every scenario supports `teardown` to remove what it made.
"""

from __future__ import annotations

import io
import json
import os
import time
import zipfile

import boto3
from botocore.exceptions import ClientError

PREFIX = "opendevops-demo"
REGION = os.environ.get("AWS_REGION", "us-east-1")
PROFILE = os.environ.get("AWS_PROFILE")
RUNTIME = "python3.12"


def log(msg: str) -> None:
    print(f"[demo] {msg}", flush=True)


def session() -> boto3.Session:
    if PROFILE:
        return boto3.Session(profile_name=PROFILE, region_name=REGION)
    return boto3.Session(region_name=REGION)


def whoami(sess: boto3.Session) -> None:
    ident = sess.client("sts").get_caller_identity()
    log(f"account={ident['Account']} region={REGION} arn={ident['Arn']}")


# --------------------------------------------------------------------------- #
# Lambda packaging + lifecycle
# --------------------------------------------------------------------------- #
def zip_handler(code: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("lambda_function.py", code)
    buf.seek(0)
    return buf.read()


def ensure_role(sess: boto3.Session, name: str, managed_arns: list[str]) -> str:
    """Create (or reuse) an IAM role assumable by Lambda with the given managed policies."""
    iam = sess.client("iam")
    assume = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }
    try:
        arn = iam.create_role(
            RoleName=name,
            AssumeRolePolicyDocument=json.dumps(assume),
            Description="OpenDevOps demo role (safe to delete)",
        )["Role"]["Arn"]
        log(f"created role {name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "EntityAlreadyExists":
            raise
        arn = iam.get_role(RoleName=name)["Role"]["Arn"]
        log(f"reusing role {name}")

    for policy_arn in managed_arns:
        iam.attach_role_policy(RoleName=name, PolicyArn=policy_arn)
    log("waiting 12s for IAM role propagation...")
    time.sleep(12)
    return arn


def delete_role(sess: boto3.Session, name: str) -> None:
    iam = sess.client("iam")
    try:
        for p in iam.list_attached_role_policies(RoleName=name)["AttachedPolicies"]:
            iam.detach_role_policy(RoleName=name, PolicyArn=p["PolicyArn"])
        for p in iam.list_role_policies(RoleName=name)["PolicyNames"]:
            iam.delete_role_policy(RoleName=name, PolicyName=p)
        iam.delete_role(RoleName=name)
        log(f"deleted role {name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise


def create_lambda(
    sess: boto3.Session,
    name: str,
    code: str,
    role_arn: str,
    *,
    timeout: int = 10,
    memory: int = 128,
    env: dict | None = None,
    vpc_config: dict | None = None,
) -> None:
    lam = sess.client("lambda")
    kwargs = dict(
        FunctionName=name,
        Runtime=RUNTIME,
        Role=role_arn,
        Handler="lambda_function.handler",
        Code={"ZipFile": zip_handler(code)},
        Timeout=timeout,
        MemorySize=memory,
        Publish=True,
    )
    if env:
        kwargs["Environment"] = {"Variables": env}
    if vpc_config:
        kwargs["VpcConfig"] = vpc_config

    # Role propagation can lag; retry the create.
    for attempt in range(6):
        try:
            lam.create_function(**kwargs)
            log(f"created lambda {name}")
            break
        except ClientError as e:
            code_ = e.response["Error"]["Code"]
            if code_ == "ResourceConflictException":
                log(f"lambda {name} exists; updating code")
                lam.update_function_code(FunctionName=name, ZipFile=zip_handler(code))
                break
            if code_ == "InvalidParameterValueException" and attempt < 5:
                log(f"role not ready, retrying ({attempt + 1}/6)...")
                time.sleep(8)
                continue
            raise
    lam.get_waiter("function_active_v2").wait(FunctionName=name)


def update_lambda_code(sess: boto3.Session, name: str, code: str) -> None:
    lam = sess.client("lambda")
    lam.update_function_code(FunctionName=name, ZipFile=zip_handler(code), Publish=True)
    lam.get_waiter("function_updated_v2").wait(FunctionName=name)
    log(f"updated code for {name}")


def delete_lambda(sess: boto3.Session, name: str) -> None:
    lam = sess.client("lambda")
    try:
        lam.delete_function(FunctionName=name)
        log(f"deleted lambda {name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise


def invoke_n(sess: boto3.Session, name: str, n: int = 5, payload: dict | None = None) -> None:
    lam = sess.client("lambda")
    body = json.dumps(payload or {}).encode()
    errors = throttles = ok = 0
    for _ in range(n):
        try:
            resp = lam.invoke(FunctionName=name, InvocationType="RequestResponse", Payload=body)
            if resp.get("FunctionError"):
                errors += 1
            else:
                ok += 1
        except ClientError as e:
            if e.response["Error"]["Code"] == "TooManyRequestsException":
                throttles += 1
            else:
                raise
        time.sleep(0.3)
    log(f"invoked {name} x{n}: ok={ok} errors={errors} throttled={throttles}")


# --------------------------------------------------------------------------- #
# Default VPC discovery (for ECS / VPC scenarios)
# --------------------------------------------------------------------------- #
def default_vpc(sess: boto3.Session) -> str:
    ec2 = sess.client("ec2")
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])["Vpcs"]
    if not vpcs:
        raise SystemExit("No default VPC found. Create one or edit the script with your VPC.")
    return vpcs[0]["VpcId"]


def default_subnets(sess: boto3.Session, vpc_id: str) -> list[str]:
    ec2 = sess.client("ec2")
    subs = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["Subnets"]
    return [s["SubnetId"] for s in subs][:2]


def parse_action(usage: str) -> str:
    import sys

    if len(sys.argv) < 2 or sys.argv[1] not in ("setup", "teardown"):
        raise SystemExit(usage)
    return sys.argv[1]
