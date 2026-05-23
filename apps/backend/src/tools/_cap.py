"""Utility: cap tool response size before the result reaches the LLM context window.

AWS tool responses (CloudWatch logs, CloudTrail events, etc.) can be very large.
Feeding them untruncated into the LLM wastes tokens and can exhaust the context window.
This module truncates oversized responses and appends a notice so the agent knows
to narrow its query.
"""

from __future__ import annotations

import json
from functools import wraps
from typing import Any

from config import settings


def cap_tool_result(result: Any, max_chars: int | None = None) -> Any:
    """Return result unchanged if within the size limit; truncate and annotate if not.

    max_chars defaults to settings.tool_response_max_chars when not supplied.
    """
    if not isinstance(result, dict):
        return result

    limit = max_chars if max_chars is not None else settings.tool_response_max_chars
    try:
        serialized = json.dumps(result)
    except (TypeError, ValueError):
        return result

    if len(serialized) <= limit:
        return result

    return {
        "_capped": True,
        "_original_chars": len(serialized),
        "_notice": (
            f"Response truncated from {len(serialized):,} to {limit:,} chars "
            "to protect the context window. Use more specific filters, shorter time "
            "ranges, or pagination to retrieve focused data."
        ),
        "_data": serialized[:limit],
    }


def with_cap(fn: Any) -> Any:
    """Wrap a tool function so its return value is passed through cap_tool_result."""
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return cap_tool_result(fn(*args, **kwargs))
    return wrapper
