"""In-memory session store: maps session_id -> message history."""

from typing import Any

_sessions: dict[str, list[dict[str, Any]]] = {}


def get_history(session_id: str) -> list[dict[str, Any]]:
    return _sessions.setdefault(session_id, [])


def append_messages(session_id: str, *messages: dict[str, Any]) -> None:
    history = _sessions.setdefault(session_id, [])
    history.extend(messages)


def clear_session(session_id: str) -> None:
    _sessions.pop(session_id, None)


def session_count() -> int:
    return len(_sessions)
