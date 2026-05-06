"""Database package — selects and exposes the right backend via the `db` singleton.

Import pattern (unchanged from the old db.py):
    from agent.db import db
"""

from __future__ import annotations

from agent.db.base import DatabaseBackend


def _create_backend() -> DatabaseBackend:
    from agent.config import settings

    backend = settings.checkpoint_backend

    if backend == "postgres":
        from agent.db.postgres import PostgresBackend
        return PostgresBackend()

    if backend == "sqlite":
        from agent.db.sqlite import SQLiteBackend
        return SQLiteBackend()

    # memory (default — zero config, no persistence)
    from agent.db.memory import MemoryBackend
    return MemoryBackend()


db: DatabaseBackend = _create_backend()

__all__ = ["db", "DatabaseBackend"]
