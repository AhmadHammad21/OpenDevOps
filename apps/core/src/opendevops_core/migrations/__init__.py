"""Core baseline SQL migrations + a source-aware runner.

The `.sql` files here define the schema that core's DB code (sessions, messages,
tool_calls, usage_events, users, organizations, alerts, incident_claims, …) reads
and writes — the baseline contract every app embedding the core must provide.

Host apps layer their own migrations on top by passing `app_migrations_dir`. Each
source ("core", "app") has an independent version sequence tracked in the
`schema_migrations(source, version)` ledger, so a core `014` and an app `014` never
collide and nothing is applied twice. Migrations are idempotent, so re-running against
a database created before the ledger existed is safe.
"""

from __future__ import annotations

from pathlib import Path

_LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    source     TEXT        NOT NULL,
    version    TEXT        NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source, version)
);
"""


def core_migrations_path() -> Path:
    """Directory holding the bundled core `.sql` migrations."""
    return Path(__file__).parent


def run_migrations(database_url: str, app_migrations_dir: Path | str | None = None) -> list[str]:
    """Apply pending migrations: core first, then the host app's, recording each in
    the `schema_migrations` ledger. Returns the list of newly applied "source/version"
    identifiers (empty when the database is already up to date).
    """
    import psycopg

    sources: list[tuple[str, Path]] = [("core", core_migrations_path())]
    if app_migrations_dir is not None:
        app_dir = Path(app_migrations_dir)
        if app_dir.exists():
            sources.append(("app", app_dir))

    applied: list[str] = []
    conn = psycopg.connect(database_url, autocommit=True)
    try:
        conn.execute(_LEDGER_DDL)
        for source, directory in sources:
            for path in sorted(directory.glob("*.sql")):
                version = path.stem
                already = conn.execute(
                    "SELECT 1 FROM schema_migrations WHERE source = %s AND version = %s",
                    (source, version),
                ).fetchone()
                if already:
                    continue
                conn.execute(path.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT INTO schema_migrations (source, version) VALUES (%s, %s)",
                    (source, version),
                )
                applied.append(f"{source}/{version}")
    finally:
        conn.close()
    return applied
