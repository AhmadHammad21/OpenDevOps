"""SNS tool: publish alerts."""

import boto3
from loguru import logger

from config import settings


def _sns_client():
    session = boto3.Session(profile_name=settings.aws_profile) if settings.aws_profile else boto3.Session()
    return session.client("sns", region_name=settings.aws_region)


def publish_sns_alert(topic_arn: str, subject: str, message: str) -> dict:
    """Publish an alert to SNS."""
    _sns_client().publish(TopicArn=topic_arn, Subject=subject[:100], Message=message)
    logger.info("SNS alert published to {}", topic_arn)
    return {"published": True, "topic_arn": topic_arn}
