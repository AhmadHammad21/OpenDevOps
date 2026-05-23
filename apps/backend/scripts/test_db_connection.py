"""
Database connectivity smoke test.

Reads .env, connects to PostgreSQL, and lists user tables.

Usage:
  uv run python scripts/test_db_connection.py
  uv run python scripts/test_db_connection.py --url-var DOCKER_DATABASE_URL
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv


def _mask_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        if parsed.password:
            netloc = parsed.netloc.replace(parsed.password, "***")
            return urlunparse(parsed._replace(netloc=netloc))
        return url
    except Exception:
        return "<invalid-url>"


def _print(msg: str) -> None:
    print(msg)


def main() -> int:
    parser = argparse.ArgumentParser(description="Test PostgreSQL connectivity and list tables")
    parser.add_argument(
        "--url-var",
        default="DATABASE_URL",
        choices=["DATABASE_URL", "DOCKER_DATABASE_URL"],
        help="Environment variable to use from .env",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent
    load_dotenv(repo_root / ".env")

    db_url = os.getenv(args.url_var)
    if not db_url:
        _print(f"ERROR: {args.url_var} is not set in .env")
        _print("Hint: set DATABASE_URL for local host access, and DOCKER_DATABASE_URL for docker-internal access")
        return 1

    _print(f"Using {args.url_var}: {_mask_url(db_url)}")

    try:
        import psycopg  # type: ignore

        with psycopg.connect(db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        current_database(),
                        current_user,
                        inet_server_addr()::text,
                        inet_server_port()
                    """
                )
                db_name, db_user, server_addr, server_port = cur.fetchone()
                _print(
                    "Connected: "
                    f"database={db_name}, user={db_user}, server={server_addr}:{server_port}"
                )

                cur.execute(
                    """
                    SELECT table_schema, table_name
                    FROM information_schema.tables
                    WHERE table_type = 'BASE TABLE'
                      AND table_schema NOT IN ('pg_catalog', 'information_schema')
                    ORDER BY table_schema, table_name
                    """
                )
                rows = cur.fetchall()

        if not rows:
            _print("No user tables found.")
            return 0

        _print(f"Found {len(rows)} table(s):")
        for schema, table in rows:
            _print(f"  - {schema}.{table}")
        return 0

    except Exception as exc:
        _print(f"ERROR: Could not connect/query database: {exc}")
        if args.url_var == "DOCKER_DATABASE_URL":
            _print("Hint: DOCKER_DATABASE_URL usually works only inside Docker network.")
            _print("Run with DATABASE_URL from host, or run this script from docker compose backend service.")
        else:
            _print("Hint: ensure docker compose db is running and port 5432 is available on host.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
