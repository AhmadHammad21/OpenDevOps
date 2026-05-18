"""Run all SQL migrations in order against the configured PostgreSQL database."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console

console = Console()


def migrate_cmd() -> None:
    """Apply all pending SQL migrations to the configured database."""
    from config import settings

    if settings.checkpoint_backend != "postgres" or not settings.database_url:
        console.print(
            "[bold red]migrate requires CHECKPOINT_BACKEND=postgres and DATABASE_URL to be set.[/bold red]"
        )
        raise typer.Exit(1)

    try:
        import psycopg
    except ImportError:
        console.print("[bold red]psycopg not installed. Run: uv add psycopg[binary,pool][/bold red]")
        raise typer.Exit(1)

    migrations_dir = Path(__file__).parent.parent.parent / "migrations"
    sql_files = sorted(migrations_dir.glob("*.sql"))
    if not sql_files:
        console.print("[yellow]No migration files found in migrations/[/yellow]")
        raise typer.Exit(0)

    console.print(f"[bold]Running {len(sql_files)} migration(s) against database...[/bold]")

    try:
        conn = psycopg.connect(settings.database_url, autocommit=True)
    except Exception as e:
        console.print(f"[bold red]Could not connect to database: {e}[/bold red]")
        raise typer.Exit(1)

    with conn:
        for path in sql_files:
            sql = path.read_text(encoding="utf-8")
            try:
                conn.execute(sql)
                console.print(f"  [green]✓[/green] {path.name}")
            except Exception as e:
                console.print(f"  [red]✗[/red] {path.name} — {e}")
                conn.close()
                raise typer.Exit(1)

    conn.close()
    console.print("[bold green]All migrations applied successfully.[/bold green]")
