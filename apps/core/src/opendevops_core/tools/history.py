"""Investigation history tools — cross-session analytics exposed to the agent."""

from __future__ import annotations

from opendevops_core.agent.db import db


async def get_investigation_history(days: int = 30) -> dict:
    """Get cross-session investigation analytics: top alarms investigated, top Lambda
    functions, recurring tool errors, and daily investigation frequency over the last
    N days. Never loads raw message content — all data is aggregated at the DB level.

    Args:
        days: Number of days to look back. Default 30.
    """
    return await db.get_history_stats(days)


async def search_past_investigations(query: str, limit: int = 10) -> dict:
    """Search past investigation sessions by keyword in title or message content.
    Returns session summaries with a short snippet — never full message bodies.

    Args:
        query: Keyword or phrase to search for (e.g. alarm name, service, error type).
        limit: Max results to return. Default 10, max 20.
    """
    results = await db.search_sessions(query, min(limit, 20))
    return {"results": results, "count": len(results)}


ALL_HISTORY_TOOLS = [get_investigation_history, search_past_investigations]
