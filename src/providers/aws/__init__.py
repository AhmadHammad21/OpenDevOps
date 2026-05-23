"""AWS cloud provider — CloudWatch, CloudTrail, ECS, Lambda, EC2, RDS, IAM."""

from __future__ import annotations

from typing import Any


class AwsProvider:
    name = "aws"

    def tools(self) -> list[Any]:
        from providers.aws.tools.cloudtrail import ALL_CLOUDTRAIL_TOOLS
        from providers.aws.tools.cloudwatch import ALL_CLOUDWATCH_TOOLS
        from providers.aws.tools.ec2 import ALL_EC2_TOOLS
        from providers.aws.tools.ecs import ALL_ECS_TOOLS
        from providers.aws.tools.iam import ALL_IAM_TOOLS
        from providers.aws.tools.lambda_ import ALL_LAMBDA_TOOLS
        from providers.aws.tools.rds import ALL_RDS_TOOLS

        return (
            ALL_CLOUDWATCH_TOOLS
            + ALL_CLOUDTRAIL_TOOLS
            + ALL_ECS_TOOLS
            + ALL_LAMBDA_TOOLS
            + ALL_EC2_TOOLS
            + ALL_RDS_TOOLS
            + ALL_IAM_TOOLS
        )

    def collect_context(self, event: dict) -> dict:
        from providers.aws.context import collect_context
        return collect_context(event)

    def check_permissions(self, region: str | None) -> dict:
        from providers.aws.permissions import check_permissions
        return check_permissions(region)

    async def polling_loop(self) -> None:
        from providers.aws.poller import polling_loop
        await polling_loop()

    async def event_consumer_loop(self) -> None:
        from providers.aws.event_consumer import event_consumer_loop
        await event_consumer_loop()


__all__ = ["AwsProvider"]
