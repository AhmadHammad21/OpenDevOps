"""Init config store — setup and event-infra state.

Single source of truth:
  - Postgres / SQLite: app_config table in the DB
  - Memory: in-memory dict (lost on restart, fine for dev)

_CACHE is the in-process copy. All sync callers (boto3 threads, etc.)
read from _CACHE — zero DB calls at runtime. Writes update _CACHE first,
then persist to DB async. The cache is seeded from DB on startup via
refresh_init_cache_from_db() called in the FastAPI lifespan.

init.json is no longer written or read.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from config import settings

_INIT_KEY = "init"
_CACHE: dict[str, Any] | None = None


def _clone(data: dict) -> dict:
    import json
    return json.loads(json.dumps(data))


def _default() -> dict:
    return {
        "initialized": False,
        "setup_complete": False,
        "event_infra_enabled": False,
        "event_infra_managed": False,
        "aws_region": settings.aws_region,
        "sqs_queue_url": "",
        "sqs_queue_arn": "",
        "sqs_dlq_url": "",
        "sqs_dlq_arn": "",
        "eventbridge_rule_arns": {},
        "permissions": {
            "cloudwatch": None,
            "cloudtrail": None,
            "ecs": None,
            "lambda": None,
            "ec2": None,
            "rds": None,
            "iam": None,
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


# ── Sync API (safe to call from boto3 thread executors) ───────────────────────

def load_init() -> dict:
    """Return a copy of the in-memory cache. Always fast — no I/O."""
    global _CACHE
    if _CACHE is None:
        _CACHE = _default()
    return _clone(_CACHE)


def save_init(data: dict) -> None:
    """Update the in-memory cache synchronously. DB persist happens via save_init_async."""
    global _CACHE
    _CACHE = _with_defaults(data)


# ── Async API (used by FastAPI route handlers) ────────────────────────────────

async def load_init_async() -> dict:
    """Load from DB into cache if not yet loaded, then return a copy."""
    global _CACHE
    try:
        from agent.db import db

        data = await db.get_app_config(_INIT_KEY)
        if data is not None:
            _CACHE = _with_defaults(data)
            return _clone(_CACHE)
        # First call with no DB record — seed DB from current cache
        if _CACHE is None:
            _CACHE = _default()
        await db.set_app_config(_INIT_KEY, _CACHE)
    except Exception as e:
        logger.debug("DB app_config unavailable, using in-memory cache: {}", e)
        if _CACHE is None:
            _CACHE = _default()
    return _clone(_CACHE)


async def save_init_async(data: dict) -> dict:
    """Update cache and persist to DB."""
    global _CACHE
    _CACHE = _with_defaults(data)
    try:
        from agent.db import db

        await db.set_app_config(_INIT_KEY, _CACHE)
    except Exception as e:
        logger.warning("Failed to persist init config to DB: {}", e)
    return _clone(_CACHE)


async def refresh_init_cache_from_db() -> dict:
    """Called on startup to warm the cache from DB before any requests arrive."""
    return await load_init_async()


async def reset_init_async() -> dict:
    """Reset to defaults in cache and DB. Does not touch AWS resources."""
    return await save_init_async(_default())


# ── Accessors (read from cache — no I/O) ─────────────────────────────────────

def is_initialized() -> bool:
    return load_init().get("setup_complete", False)


def is_event_infra_enabled() -> bool:
    data = load_init()
    return bool(data.get("event_infra_enabled") and data.get("sqs_queue_url"))


def get_runtime_aws_region() -> str:
    return str(load_init().get("aws_region") or settings.aws_region)


def get_runtime_sqs_queue_url() -> str:
    return str(settings.sqs_queue_url or load_init().get("sqs_queue_url") or "")


