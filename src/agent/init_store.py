"""Init config store — persists setup and event-infra state.

SQLite/Postgres deployments store the canonical value in the app_config table.
The JSON file remains a local cache and fallback for memory/dev mode and sync AWS tool code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from config import settings

_INIT_FILE = Path(settings.data_dir) / "init.json"
_INIT_KEY = "init"
_CACHE: dict[str, Any] | None = None


def _clone(data: dict) -> dict:
    return json.loads(json.dumps(data))


def _default() -> dict:
    return {
        "initialized": False,
        "setup_complete": False,
        "event_infra_enabled": False,
        "event_infra_managed": False,
        "sns_topic_arn": "",
        "aws_region": settings.aws_region,
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


def _with_defaults(data: dict) -> dict:
    merged = _default()
    permissions = {**merged["permissions"], **data.get("permissions", {})}
    merged.update(data)
    merged["permissions"] = permissions

    legacy_initialized = bool(data.get("initialized", False))
    merged["setup_complete"] = bool(data.get("setup_complete", legacy_initialized))
    merged["event_infra_enabled"] = bool(
        data.get(
            "event_infra_enabled",
            legacy_initialized
            and bool(data.get("sqs_queue_url") or data.get("eventbridge_rule_arns")),
        )
    )
    merged["event_infra_managed"] = bool(
        data.get(
            "event_infra_managed",
            bool(data.get("eventbridge_rule_arns") or data.get("sqs_queue_arn")),
        )
    )
    merged["initialized"] = merged["setup_complete"]
    return merged


def _read_file() -> dict | None:
    if not _INIT_FILE.exists():
        return None
    try:
        return json.loads(_INIT_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to read init.json, returning defaults: {}", e)
        return None


def _write_file(data: dict) -> None:
    _INIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    _INIT_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.debug("Saved init.json")


def load_init() -> dict:
    global _CACHE
    if _CACHE is None:
        _CACHE = _with_defaults(_read_file() or {})
    return _clone(_CACHE)


def save_init(data: dict) -> None:
    global _CACHE
    _CACHE = _with_defaults(data)
    _write_file(_CACHE)


async def load_init_async() -> dict:
    global _CACHE
    try:
        from agent.db import db

        data = await db.get_app_config(_INIT_KEY)
        if data is not None:
            _CACHE = _with_defaults(data)
            _write_file(_CACHE)
            return _clone(_CACHE)
        file_data = load_init()
        await db.set_app_config(_INIT_KEY, file_data)
        return file_data
    except Exception as e:
        logger.debug("DB init config unavailable, using file fallback: {}", e)
    return load_init()


async def save_init_async(data: dict) -> dict:
    save_init(data)
    try:
        from agent.db import db

        await db.set_app_config(_INIT_KEY, load_init())
    except Exception as e:
        logger.warning("Failed to persist init config to DB: {}", e)
    return load_init()


async def refresh_init_cache_from_db() -> dict:
    return await load_init_async()


def is_initialized() -> bool:
    return load_init().get("setup_complete", False)


def is_event_infra_enabled() -> bool:
    data = load_init()
    return bool(data.get("event_infra_enabled") and data.get("sqs_queue_url"))


def get_runtime_aws_region() -> str:
    return str(load_init().get("aws_region") or settings.aws_region)


def get_runtime_sqs_queue_url() -> str:
    return str(settings.sqs_queue_url or load_init().get("sqs_queue_url") or "")


def get_runtime_sns_topic_arn() -> str:
    return str(settings.sns_topic_arn or load_init().get("sns_topic_arn") or "")
