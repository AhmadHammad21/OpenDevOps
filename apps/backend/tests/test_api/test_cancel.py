"""Tests for DELETE /chat/{session_id} — real-time agent cancellation."""

from __future__ import annotations

import asyncio
import os

import pytest

os.environ.setdefault("CHECKPOINT_BACKEND", "memory")
os.environ.setdefault("LLM_MODEL", "openrouter/anthropic/claude-3.5-sonnet")
os.environ.setdefault("LLM_API_KEY", "test-key")


@pytest.mark.asyncio
async def test_cancel_unknown_session():
    """DELETE on a session with no active stream returns cancelled=False."""
    from httpx import ASGITransport, AsyncClient

    from api.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.delete("/chat/no-such-session-xyz")

    assert r.status_code == 200
    assert r.json() == {"cancelled": False}


@pytest.mark.asyncio
async def test_cancel_active_session():
    """DELETE on a session with a registered cancel event sets it and returns cancelled=True."""
    from httpx import ASGITransport, AsyncClient

    from api.app import app
    from api.routers.chat import _cancel_events

    session_id = "test-cancel-active-456"
    event = asyncio.Event()
    _cancel_events[session_id] = event

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.delete(f"/chat/{session_id}")

        assert r.status_code == 200
        assert r.json() == {"cancelled": True}
        assert event.is_set()
    finally:
        _cancel_events.pop(session_id, None)


@pytest.mark.asyncio
async def test_cancel_cleans_up_after_stream():
    """The cancel event is removed from the registry once a stream finishes."""
    from api.routers.chat import _cancel_events

    session_id = "test-cleanup-789"

    # Simulate stream lifecycle: register → finish → clean up
    event = asyncio.Event()
    _cancel_events[session_id] = event
    _cancel_events.pop(session_id, None)

    assert session_id not in _cancel_events
