"""
M3 — ECS service won't stabilize (bad image tag).

Creates a Fargate cluster + service pointing at a non-existent image tag, so
tasks fail to pull and the deployment never reaches a steady state. Service
events fill with "CannotPullContainerError".

HEAVIER + COSTS A LITTLE while running (Fargate). Tear down when done.
Uses your default VPC subnets and a permissive demo security group.

Ask the agent:  "the ECS service opendevops-demo-svc won't come up, why?"
Expect: list_ecs_clusters -> describe_ecs_service (failed deployment + events).

  uv run python demos/m3_ecs_wont_stabilize.py setup
  uv run python demos/m3_ecs_wont_stabilize.py teardown
"""

from __future__ import annotations

import json
import time

import _common as c
from botocore.exceptions import ClientError

CLUSTER = f"{c.PREFIX}-cluster"
SERVICE = f"{c.PREFIX}-svc"
TASKDEF = f"{c.PREFIX}-task"
EXEC_ROLE = f"{c.PREFIX}-ecs-exec-role"
SG_NAME = f"{c.PREFIX}-ecs-sg"
EXEC_POLICY = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
BAD_IMAGE = "public.ecr.aws/nginx/nginx:this-tag-does-not-exist-9999"


def _ecs_exec_role(sess: c.boto3.Session) -> str:
    iam = sess.client("iam")
    trust = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }
    try:
        arn = iam.create_role(
            RoleName=EXEC_ROLE, AssumeRolePolicyDocument=json.dumps(trust)
        )["Role"]["Arn"]
    except ClientError as e:
        if e.response["Error"]["Code"] != "EntityAlreadyExists":
            raise
        arn = iam.get_role(RoleName=EXEC_ROLE)["Role"]["Arn"]
    iam.attach_role_policy(RoleName=EXEC_ROLE, PolicyArn=EXEC_POLICY)
    time.sleep(12)
    return arn


def _sg(sess: c.boto3.Session, vpc_id: str) -> str:
    ec2 = sess.client("ec2")
    try:
        return ec2.create_security_group(
            GroupName=SG_NAME, Description="OpenDevOps demo", VpcId=vpc_id
        )["GroupId"]
    except ClientError as e:
        if e.response["Error"]["Code"] != "InvalidGroup.Duplicate":
            raise
        sgs = ec2.describe_security_groups(
            Filters=[{"Name": "group-name", "Values": [SG_NAME]}]
        )["SecurityGroups"]
        return sgs[0]["GroupId"]


def setup() -> None:
    sess = c.session()
    c.whoami(sess)
    ecs = sess.client("ecs")

    exec_arn = _ecs_exec_role(sess)
    vpc = c.default_vpc(sess)
    subnets = c.default_subnets(sess, vpc)
    sg = _sg(sess, vpc)

    ecs.create_cluster(clusterName=CLUSTER)
    c.log(f"created cluster {CLUSTER}")

    ecs.register_task_definition(
        family=TASKDEF,
        requiresCompatibilities=["FARGATE"],
        networkMode="awsvpc",
        cpu="256",
        memory="512",
        executionRoleArn=exec_arn,
        containerDefinitions=[
            {"name": "app", "image": BAD_IMAGE, "essential": True}
        ],
    )
    c.log(f"registered task def with bad image: {BAD_IMAGE}")

    ecs.create_service(
        cluster=CLUSTER,
        serviceName=SERVICE,
        taskDefinition=TASKDEF,
        desiredCount=1,
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": subnets,
                "securityGroups": [sg],
                "assignPublicIp": "ENABLED",
            }
        },
    )
    c.log("created service — it will keep trying to pull and failing")
    c.log("wait ~2 min for failure events, then: 'why won't opendevops-demo-svc come up?'")


def teardown() -> None:
    sess = c.session()
    ecs = sess.client("ecs")
    try:
        ecs.update_service(cluster=CLUSTER, service=SERVICE, desiredCount=0)
        ecs.delete_service(cluster=CLUSTER, service=SERVICE, force=True)
        c.log("deleted service")
    except ClientError as e:
        c.log(f"service delete skipped: {e.response['Error']['Code']}")
    try:
        ecs.delete_cluster(cluster=CLUSTER)
        c.log("deleted cluster")
    except ClientError as e:
        c.log(f"cluster delete skipped: {e.response['Error']['Code']}")

    ec2 = sess.client("ec2")
    try:
        sgs = ec2.describe_security_groups(
            Filters=[{"Name": "group-name", "Values": [SG_NAME]}]
        )["SecurityGroups"]
        for s in sgs:
            ec2.delete_security_group(GroupId=s["GroupId"])
            c.log("deleted security group")
    except ClientError as e:
        c.log(f"sg delete skipped: {e.response['Error']['Code']}")
    c.delete_role(sess, EXEC_ROLE)


if __name__ == "__main__":
    action = c.parse_action(__doc__)
    setup() if action == "setup" else teardown()
