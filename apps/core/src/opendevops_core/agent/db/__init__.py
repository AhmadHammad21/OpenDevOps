"""Database package — selects and exposes the right backend via the `db` singleton.

Import pattern (unchanged from the old db.py):
    from opendevops_core.agent.db import db
"""

from __future__ import annotations

from opendevops_core.agent.db.base import DatabaseBackend


def _create_backend() -> DatabaseBackend:
    from opendevops_core.config import settings

    backend = settings.checkpoint_backend

    if backend == "postgres":
        from opendevops_core.agent.db.postgres import PostgresBackend

        return PostgresBackend()

    if backend == "sqlite":
        from opendevops_core.agent.db.sqlite import SQLiteBackend

        return SQLiteBackend()

    # memory (default — zero config, no persistence)
    from opendevops_core.agent.db.memory import MemoryBackend

    return MemoryBackend()


db: DatabaseBackend = _create_backend()

__all__ = ["db", "DatabaseBackend"]
