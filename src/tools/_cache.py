"""Shared TTL cache for AWS tool responses.

All tool functions use this cache to avoid redundant AWS API calls within a
short window. The cache key always includes the AWS profile + region so that
a process serving multiple AWS accounts never returns one account's data to
another (relevant for multi-tenant deployments).

To swap to Redis later, replace _cache and _tool_key here — tool files need
no changes.
"""

from __future__ import annotations

import json

from cachetools import TTLCache
from cachetools.keys import hashkey

from agent.config import settings

# 256 entries max, each lives 2 minutes.
_cache: TTLCache = TTLCache(maxsize=256, ttl=120)


def tool_cache_key(*args, **kwargs) -> tuple:
    """Build a hashable cache key from function args + current AWS context.

    Converts unhashable args (list, dict) to stable JSON strings so they can
    be used as dict keys. Prefixes every key with (aws_profile, aws_region)
    so results from different AWS accounts are never mixed.
    """
    def _h(v):
        if isinstance(v, (list, dict)):
            return json.dumps(v, sort_keys=True)
        return v

    return hashkey(
        settings.aws_profile,
        settings.aws_region,
        *[_h(a) for a in args],
        **{k: _h(v) for k, v in kwargs.items()},
    )
