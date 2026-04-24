"""
Database setup script — creates tables and initialises the LangGraph checkpointer.

Usage:
    uv run python scripts/setup_db.py

Reads DATABASE_URL from .env (or the environment).
Safe to run multiple times — all statements use IF NOT EXISTS / ON CONFLICT.
"""

import asyncio
import sys
from pathlib import Path

# ── Make sure src/ is on the path when run from the repo root ────────────────
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from agent.config import settings  # noqa: E402 — must come after load_dotenv


def _banner(msg: str) -> None:
    print(f"\n\033[1;36m{'─' * 60}\033[0m")
    print(f"\033[1;36m  {msg}\033[0m")
    print(f"\033[1;36m{'─' * 60}\033[0m")


def _ok(msg: str) -> None:
    print(f"  \033[32m✓\033[0m  {msg}")


def _err(msg: str) -> None:
    print(f"  \033[31m✗\033[0m  {msg}")


def _info(msg: str) -> None:
    print(f"  \033[90m→\033[0m  {msg}")


# ── Sync migration (psycopg3 sync API — simpler for a one-shot script) ───────

def run_migration(database_url: str) -> None:
    import psycopg  # type: ignore

    migration_file = Path(__file__).parent.parent / "migrations" / "001_initial.sql"
    sql = migration_file.read_text(encoding="utf-8")

    _info(f"Connecting to {_mask_url(database_url)}")
    with psycopg.connect(database_url, autocommit=True) as conn:
        _ok("Connected")
        _info("Running migrations/001_initial.sql …")
        conn.execute(sql)
        _ok("App tables created (IF NOT EXISTS — safe to re-run)")


# ── Async LangGraph checkpointer setup ───────────────────────────────────────

async def run_checkpointer_setup(database_url: str) -> None:
    from psycopg_pool import AsyncConnectionPool  # type: ignore
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # type: ignore

    _info("Setting up LangGraph checkpointer tables …")
    async with await AsyncConnectionPool(conninfo=database_url, open=True) as pool:
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
    _ok("LangGraph checkpointer tables ready")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mask_url(url: str) -> str:
    """Hide password in the URL for display."""
    try:
        from urllib.parse import urlparse, urlunparse
        p = urlparse(url)
        masked = p._replace(netloc=f"{p.username}:***@{p.hostname}:{p.port or 5432}")
        return urlunparse(masked)
    except Exception:
        return "***"


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    _banner("OpenDevOps — Database Setup")

    if not settings.database_url:
        _err("DATABASE_URL is not set in .env")
        print("\n  Add this to your .env file:")
        print("  DATABASE_URL=postgresql://user:password@localhost:5432/opendevops\n")
        sys.exit(1)

    url = settings.database_url

    try:
        run_migration(url)
    except Exception as e:
        _err(f"Migration failed: {e}")
        print("\n  Tip: make sure the database exists and DATABASE_URL is correct.")
        print("  To create the database with Docker:")
        print("    docker run -d --name opendevops-pg \\")
        print("      -e POSTGRES_DB=opendevops \\")
        print("      -e POSTGRES_USER=dev \\")
        print("      -e POSTGRES_PASSWORD=dev \\")
        print("      -p 5432:5432 postgres:16\n")
        sys.exit(1)

    try:
        asyncio.run(run_checkpointer_setup(url))
    except Exception as e:
        _err(f"Checkpointer setup failed: {e}")
        sys.exit(1)

    _banner("Setup complete")
    print("  You can now start the server:")
    print("  \033[1muv run uvicorn src.api.app:app --reload\033[0m\n")


if __name__ == "__main__":
    main()
