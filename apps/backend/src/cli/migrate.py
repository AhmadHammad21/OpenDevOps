"""Apply core + app SQL migrations against the configured PostgreSQL database."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

console = Console()

# App-specific migrations live here (none yet — all current schema is core baseline).
# New OSS-app-only migrations go in this directory; core migrations ship with the package.
_APP_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "migrations"


def migrate_cmd() -> None:
    """Apply all pending SQL migrations to the configured database."""
    from config import settings

    if settings.checkpoint_backend != "postgres" or not settings.database_url:
        console.print(
            "[bold red]migrate requires CHECKPOINT_BACKEND=postgres and "
            "DATABASE_URL to be set.[/bold red]"
        )
        raise typer.Exit(1)

    from opendevops_core.migrations import run_migrations

    try:
        applied = run_migrations(settings.database_url, _APP_MIGRATIONS_DIR)
    except Exception as e:
        console.print(f"[bold red]Migration failed: {e}[/bold red]")
        raise typer.Exit(1)

    if applied:
        for ident in applied:
            console.print(f"  [green]✓[/green] {ident}")
        console.print(f"[bold green]Applied {len(applied)} migration(s).[/bold green]")
    else:
        console.print(
            "[bold green]Database already up to date — no pending migrations.[/bold green]"
        )
