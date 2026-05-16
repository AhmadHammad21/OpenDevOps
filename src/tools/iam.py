"""IAM tool: read-only role and policy inspection."""

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from loguru import logger

from agent.init_store import get_runtime_aws_region
from config import settings
from tools._cache import tool_cached


def _iam_client() -> Any:
    session = (
        boto3.Session(profile_name=settings.aws_profile)
        if settings.aws_profile
        else boto3.Session()
    )
    return session.client("iam", region_name=get_runtime_aws_region())


def _sts_client() -> Any:
    session = (
        boto3.Session(profile_name=settings.aws_profile)
        if settings.aws_profile
        else boto3.Session()
    )
    return session.client("sts", region_name=get_runtime_aws_region())


@tool_cached
def get_caller_identity() -> dict:
    """Return the current AWS caller identity: account ID, user/role ARN, and user ID."""
    try:
        client = _sts_client()
        resp = client.get_caller_identity()
        return {
            "account_id": resp.get("Account", ""),
            "arn": resp.get("Arn", ""),
            "user_id": resp.get("UserId", ""),
        }
    except (BotoCoreError, ClientError) as e:
        logger.error("get_caller_identity failed: {}", e)
        return {"error": str(e)}


@tool_cached
def get_iam_role_policies(role_name: str) -> dict:
    """List policies attached to an IAM role.

    Args:
        role_name: IAM role name.
    """
    try:
        client = _iam_client()
        attached = client.list_attached_role_policies(RoleName=role_name)
        inline = client.list_role_policies(RoleName=role_name)
        return {
            "role": role_name,
            "attached_policies": [
                {"name": p["PolicyName"], "arn": p["PolicyArn"]}
                for p in attached.get("AttachedPolicies", [])
            ],
            "inline_policy_names": inline.get("PolicyNames", []),
        }
    except (BotoCoreError, ClientError) as e:
        logger.error("get_iam_role_policies failed: {}", e)
        return {"error": str(e)}


ALL_IAM_TOOLS = [get_caller_identity, get_iam_role_policies]
