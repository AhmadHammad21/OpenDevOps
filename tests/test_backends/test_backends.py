"""Backend tests — same assertions run against memory, sqlite, and (optionally) postgres.

memory + sqlite: always run, no external services needed.
postgres:        skipped unless DATABASE_URL env var is set.
"""

from __future__ import annotations

import os
import pytest
import pytest_asyncio

from agent.db.base import DatabaseBackend

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(params=["memory", "sqlite"])
async def backend(request, tmp_path) -> DatabaseBackend:
    """Parametrised fixture: runs every test twice — once per local backend."""
    if request.param == "memory":
        from agent.db.memory import MemoryBackend
        b = MemoryBackend()
    else:
        from agent.db.sqlite import SQLiteBackend
        b = SQLiteBackend()
        b._path = str(tmp_path / "agent.db")  # isolated per test

    await b.init()
    yield b
    await b.close()


@pytest_asyncio.fixture
async def pg_backend() -> DatabaseBackend:
    """PostgreSQL backend — skipped unless DATABASE_URL is set."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set — skipping postgres backend tests")

    from agent.db.postgres import PostgresBackend
    from config import settings
    settings.database_url = url

    b = PostgresBackend()
    await b.init()
    yield b
    await b.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

SESSION_ID = "00000000-0000-0000-0000-000000000001"
SESSION_ID2 = "00000000-0000-0000-0000-000000000002"


async def _seed_session(b: DatabaseBackend, session_id: str = SESSION_ID) -> str:
    """Create a session and return its ID."""
    await b.upsert_session(session_id, model="test-model", aws_region="us-east-1", title="Test")
    return session_id


async def _seed_messages(b: DatabaseBackend, session_id: str = SESSION_ID) -> tuple[str, str]:
    """Add one user + one assistant message, return their IDs."""
    user_id = await b.save_message(session_id, "user", "What is wrong with Lambda?")
    asst_id = await b.save_message(session_id, "assistant", "Investigating now…")
    return user_id, asst_id


# ── Init ──────────────────────────────────────────────────────────────────────


async def test_init_returns_checkpointer(backend: DatabaseBackend):
    assert backend.checkpointer is not None


# ── Session round-trip ────────────────────────────────────────────────────────


async def test_upsert_and_list_sessions(backend: DatabaseBackend):
    await _seed_session(backend)
    sessions = await backend.list_sessions()
    assert len(sessions) == 1
    assert sessions[0]["id"] == SESSION_ID
    assert sessions[0]["title"] == "Test"
    assert sessions[0]["model"] == "test-model"


async def test_upsert_is_idempotent(backend: DatabaseBackend):
    await _seed_session(backend)
    await _seed_session(backend)  # second call must not duplicate
    assert len(await backend.list_sessions()) == 1


async def test_list_sessions_is_empty_by_default(backend: DatabaseBackend):
    assert await backend.list_sessions() == []


# ── Message round-trip ────────────────────────────────────────────────────────


async def test_save_and_get_messages(backend: DatabaseBackend):
    await _seed_session(backend)
    user_id, asst_id = await _seed_messages(backend)

    messages = await backend.get_messages(SESSION_ID)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "What is wrong with Lambda?"
    assert messages[1]["role"] == "assistant"


async def test_save_message_returns_id(backend: DatabaseBackend):
    await _seed_session(backend)
    msg_id = await backend.save_message(SESSION_ID, "user", "hello")
    assert isinstance(msg_id, str) and len(msg_id) > 0


async def test_get_messages_unknown_session_returns_empty(backend: DatabaseBackend):
    result = await backend.get_messages("00000000-0000-0000-0000-000000000099")
    assert result == []


# ── Tool calls ────────────────────────────────────────────────────────────────


async def test_tool_call_appears_in_messages(backend: DatabaseBackend):
    await _seed_session(backend)
    _, asst_id = await _seed_messages(backend)

    await backend.save_tool_call(
        SESSION_ID, asst_id,
        tool_name="get_alarms",
        args={"state": "ALARM"},
        result={"alarms": []},
    )

    messages = await backend.get_messages(SESSION_ID)
    asst_msg = next(m for m in messages if m["role"] == "assistant")
    assert len(asst_msg["tool_calls"]) == 1
    assert asst_msg["tool_calls"][0]["tool_name"] == "get_alarms"


async def test_tool_call_error_field_captured(backend: DatabaseBackend):
    await _seed_session(backend)
    _, asst_id = await _seed_messages(backend)

    await backend.save_tool_call(
        SESSION_ID, asst_id,
        tool_name="get_alarms",
        args={},
        result={"error": "permission denied"},
    )

    messages = await backend.get_messages(SESSION_ID)
    asst_msg = next(m for m in messages if m["role"] == "assistant")
    assert asst_msg["tool_calls"][0]["error"] == "permission denied"


# ── Soft delete ───────────────────────────────────────────────────────────────


async def test_delete_hides_session_from_list(backend: DatabaseBackend):
    await _seed_session(backend)
    await backend.delete_session(SESSION_ID)
    assert await backend.list_sessions() == []


async def test_delete_hides_messages(backend: DatabaseBackend):
    await _seed_session(backend)
    await _seed_messages(backend)
    await backend.delete_session(SESSION_ID)
    assert await backend.get_messages(SESSION_ID) == []


# ── Usage events ──────────────────────────────────────────────────────────────


async def test_save_usage_event_does_not_raise(backend: DatabaseBackend):
    await _seed_session(backend)
    _, asst_id = await _seed_messages(backend)
    await backend.save_usage_event(
        SESSION_ID, asst_id,
        model="test-model",
        input_tokens=100, output_tokens=200,
        cost_usd=0.001, latency_ms=1500,
        tool_call_count=2,
    )


# ── Dashboard stats ───────────────────────────────────────────────────────────

_DASHBOARD_KEYS = {"summary", "activity", "top_tools", "service_breakdown", "recent_sessions", "root_causes"}
_SUMMARY_KEYS   = {"total_sessions", "total_queries", "total_tool_calls", "total_tool_errors",
                   "total_input_tokens", "total_output_tokens", "total_cost_usd", "avg_latency_ms"}


async def test_dashboard_stats_has_required_keys(backend: DatabaseBackend):
    stats = await backend.get_dashboard_stats()
    assert set(stats.keys()) == _DASHBOARD_KEYS
    assert set(stats["summary"].keys()) == _SUMMARY_KEYS


async def test_dashboard_stats_counts_sessions(backend: DatabaseBackend):
    await _seed_session(backend)
    stats = await backend.get_dashboard_stats()
    assert stats["summary"]["total_sessions"] == 1


async def test_dashboard_stats_counts_queries(backend: DatabaseBackend):
    await _seed_session(backend)
    await _seed_messages(backend)
    stats = await backend.get_dashboard_stats()
    assert stats["summary"]["total_queries"] == 1  # only user messages


# ── History stats ─────────────────────────────────────────────────────────────

_HISTORY_KEYS = {"days", "top_alarms", "top_lambdas", "recurring_errors", "trend"}


async def test_history_stats_has_required_keys(backend: DatabaseBackend):
    stats = await backend.get_history_stats(days=7)
    assert set(stats.keys()) == _HISTORY_KEYS
    assert stats["days"] == 7


async def test_history_stats_empty_by_default(backend: DatabaseBackend):
    stats = await backend.get_history_stats()
    assert stats["top_alarms"] == []
    assert stats["top_lambdas"] == []
    assert stats["trend"] == []


# ── Search ────────────────────────────────────────────────────────────────────


async def test_search_finds_matching_content(backend: DatabaseBackend):
    await _seed_session(backend)
    await backend.save_message(SESSION_ID, "user", "Lambda throttling in us-east-1")

    results = await backend.search_sessions("throttling")
    assert len(results) == 1
    assert results[0]["id"] == SESSION_ID


async def test_search_empty_query_returns_empty(backend: DatabaseBackend):
    await _seed_session(backend)
    await _seed_messages(backend)
    assert await backend.search_sessions("") == []


async def test_search_no_match_returns_empty(backend: DatabaseBackend):
    await _seed_session(backend)
    await backend.save_message(SESSION_ID, "user", "CloudWatch alarm fired")
    assert await backend.search_sessions("kubernetes") == []


async def test_search_finds_by_title(backend: DatabaseBackend):
    await backend.upsert_session(SESSION_ID, "test-model", "us-east-1", title="Lambda deep-dive")
    await backend.save_message(SESSION_ID, "user", "something unrelated")

    results = await backend.search_sessions("deep-dive")
    assert len(results) == 1


# ── PostgreSQL-specific tests ─────────────────────────────────────────────────
# These re-run the same core assertions against a live Postgres instance.
# Skipped automatically when DATABASE_URL is not set.


async def test_pg_init_returns_checkpointer(pg_backend: DatabaseBackend):
    assert pg_backend.checkpointer is not None


async def test_pg_session_roundtrip(pg_backend: DatabaseBackend):
    await pg_backend.upsert_session(SESSION_ID2, "gpt-4o", "eu-west-1", title="PG test")
    sessions = await pg_backend.list_sessions()
    ids = [s["id"] for s in sessions]
    assert SESSION_ID2 in ids
    await pg_backend.delete_session(SESSION_ID2)


async def test_pg_message_roundtrip(pg_backend: DatabaseBackend):
    await pg_backend.upsert_session(SESSION_ID2, "gpt-4o", "eu-west-1")
    uid = await pg_backend.save_message(SESSION_ID2, "user", "PG message test")
    messages = await pg_backend.get_messages(SESSION_ID2)
    assert any(m["id"] == uid for m in messages)
    await pg_backend.delete_session(SESSION_ID2)


async def test_pg_dashboard_stats_keys(pg_backend: DatabaseBackend):
    stats = await pg_backend.get_dashboard_stats()
    assert set(stats.keys()) == _DASHBOARD_KEYS
