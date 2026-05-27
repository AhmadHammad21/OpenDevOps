"""
H3 — Lambda in a VPC with no egress (network root cause).

Puts a Lambda in your default VPC behind a security group that has NO outbound
rules. The handler calls an external HTTPS endpoint and hangs until it times out.
Nothing about the code or timeout config is obviously wrong — the cause is the
network path. The agent must notice vpc_enabled + the connection timeout pattern.

Ask the agent:  "opendevops-demo-egress times out calling an external API, why?"
Expect: get_log_events (connect timeout) + get_lambda_function_config
(vpc_enabled: true). Bonus if it reasons about the SG having no egress.

NOTE: teardown can take a few minutes — deleting a VPC Lambda releases ENIs
asynchronously, so the security group delete is retried until the ENIs clear.

  uv run python demos/h3_lambda_vpc_no_egress.py setup
  uv run python demos/h3_lambda_vpc_no_egress.py teardown
"""

from __future__ import annotations

import time

import _common as c
from botocore.exceptions import ClientError

FN = f"{c.PREFIX}-egress"
ROLE = f"{c.PREFIX}-vpc-role"
SG_NAME = f"{c.PREFIX}-no-egress-sg"
VPC_EXEC = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"

CODE = """
import urllib.request
def handler(event, context):
    # No NAT / no egress rule => this connection never establishes.
    with urllib.request.urlopen("https://example.com", timeout=5) as r:
        return {"status": r.status}
"""


def _no_egress_sg(sess: c.boto3.Session, vpc_id: str) -> str:
    ec2 = sess.client("ec2")
    try:
        sg = ec2.create_security_group(
            GroupName=SG_NAME, Description="OpenDevOps demo no egress", VpcId=vpc_id
        )["GroupId"]
    except ClientError as e:
        if e.response["Error"]["Code"] != "InvalidGroup.Duplicate":
            raise
        sg = ec2.describe_security_groups(
            Filters=[{"Name": "group-name", "Values": [SG_NAME]}]
        )["SecurityGroups"][0]["GroupId"]
    # Remove the default allow-all egress rule so there is truly no outbound path.
    try:
        ec2.revoke_security_group_egress(
            GroupId=sg,
            IpPermissions=[{"IpProtocol": "-1", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}],
        )
        c.log("revoked default egress rule (no outbound allowed)")
    except ClientError as e:
        c.log(f"egress revoke skipped: {e.response['Error']['Code']}")
    return sg


def setup() -> None:
    sess = c.session()
    c.whoami(sess)
    vpc = c.default_vpc(sess)
    subnets = c.default_subnets(sess, vpc)
    sg = _no_egress_sg(sess, vpc)
    role = c.ensure_role(sess, ROLE, [VPC_EXEC])

    c.create_lambda(
        sess,
        FN,
        CODE,
        role,
        timeout=15,
        vpc_config={"SubnetIds": subnets, "SecurityGroupIds": [sg]},
    )
    c.invoke_n(sess, FN, n=4)
    c.log("DONE. Investigate: 'opendevops-demo-egress times out calling an API, why?'")


def teardown() -> None:
    sess = c.session()
    c.delete_lambda(sess, FN)
    c.delete_role(sess, ROLE)

    ec2 = sess.client("ec2")
    sgs = ec2.describe_security_groups(
        Filters=[{"Name": "group-name", "Values": [SG_NAME]}]
    )["SecurityGroups"]
    for s in sgs:
        for attempt in range(10):
            try:
                ec2.delete_security_group(GroupId=s["GroupId"])
                c.log("deleted security group")
                break
            except ClientError as e:
                if e.response["Error"]["Code"] == "DependencyViolation":
                    c.log(f"ENIs still releasing, retry in 30s ({attempt + 1}/10)...")
                    time.sleep(30)
                    continue
                raise


if __name__ == "__main__":
    action = c.parse_action(__doc__)
    setup() if action == "setup" else teardown()
