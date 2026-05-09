"""Init config store — persists initialization state to <data_dir>/init.json."""

import json
from pathlib import Path

from loguru import logger

from config import settings

_INIT_FILE = Path(settings.data_dir) / "init.json"

_DEFAULT: dict = {
    "initialized": False,
    "sns_topic_arn": "",
    "aws_region": "us-east-1",
    "sqs_queue_url": "",
    "sqs_queue_arn": "",
    "eventbridge_rule_arns": {},
    "permissions": {
        "cloudwatch": None,
        "cloudtrail": None,
        "ecs": None,
        "lambda": None,
        "ec2": None,
        "rds": None,
        "iam": None,
        "sns": None,
        "sqs": None,
        "events": None,
    },
    "skipped_services": [],
}


def load_init() -> dict:
    if not _INIT_FILE.exists():
        return json.loads(json.dumps(_DEFAULT))
    try:
        return json.loads(_INIT_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to read init.json, returning defaults: {}", e)
        return json.loads(json.dumps(_DEFAULT))


def save_init(data: dict) -> None:
    _INIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    _INIT_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.debug("Saved init.json")


def is_initialized() -> bool:
    return load_init().get("initialized", False)
