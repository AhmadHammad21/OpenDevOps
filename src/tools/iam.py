"""IAM tool: read-only role and policy inspection."""

import logging
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from agent.config import settings
from tools.base import BaseTool

logger = logging.getLogger(__name__)


def _iam_client() -> Any:
    session = boto3.Session(profile_name=settings.aws_profile) if settings.aws_profile else boto3.Session()
    return session.client("iam", region_name=settings.aws_region)


def _sts_client() -> Any:
    session = boto3.Session(profile_name=settings.aws_profile) if settings.aws_profile else boto3.Session()
    return session.client("sts", region_name=settings.aws_region)


class GetCallerIdentityTool(BaseTool):
    name = "get_caller_identity"
    description = "Return the current AWS caller identity: account ID, user/role ARN, and user ID."

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    def run(self, **_: Any) -> dict[str, Any]:
        try:
            client = _sts_client()
            resp = client.get_caller_identity()
            return {
                "account_id": resp.get("Account", ""),
                "arn": resp.get("Arn", ""),
                "user_id": resp.get("UserId", ""),
            }
        except (BotoCoreError, ClientError) as e:
            logger.error("get_caller_identity failed: %s", e)
            return {"error": str(e)}


class GetRolePolicies(BaseTool):
    name = "get_iam_role_policies"
    description = "List policies attached to an IAM role."

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "role_name": {"type": "string", "description": "IAM role name."}
                },
                "required": ["role_name"],
            },
        }

    def run(self, role_name: str, **_: Any) -> dict[str, Any]:
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
            logger.error("get_iam_role_policies failed: %s", e)
            return {"error": str(e)}


ALL_IAM_TOOLS: list[BaseTool] = [GetCallerIdentityTool(), GetRolePolicies()]
