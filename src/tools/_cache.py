"""Shared TTL cache for AWS tool responses.

All tool functions use the @tool_cached decorator. The cache key includes the
function name + AWS profile + region so:
  - different functions with identical args never collide
  - results from different AWS accounts are never mixed (multi-tenant safe)

To swap to Redis later, replace _cache and tool_cached here — tool files need
no changes.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, TypeVar

from cachetools import TTLCache, cached
from cachetools.keys import hashkey

from config import settings

F = TypeVar("F", bound=Callable[..., Any])

# 256 entries max, each lives 2 minutes.
_cache: TTLCache = TTLCache(maxsize=256, ttl=120)


def tool_cached(fn: F) -> F:
    """Cache decorator for AWS tool functions.

    Includes the function name in the key so zero-argument functions like
    list_lambda_functions() and describe_rds_instances() never collide.
    """
    fn_name = fn.__name__

    def _key(*args, **kwargs) -> tuple:
        def _h(v: Any) -> Any:
            return json.dumps(v, sort_keys=True) if isinstance(v, (list, dict)) else v

        return hashkey(
            fn_name,
            settings.aws_profile,
            settings.aws_region,
            *[_h(a) for a in args],
            **{k: _h(v) for k, v in kwargs.items()},
        )

    return cached(_cache, key=_key)(fn)  # type: ignore[return-value]
