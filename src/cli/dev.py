import sys
from typing import Annotated

import typer
import uvicorn
from rich.console import Console

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

console = Console()


def dev_cmd(
    host: Annotated[str, typer.Option("--host", help="Bind host.")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", "-p", help="Port to listen on.")] = 8000,
) -> None:
    """Start the development server with hot reload enabled."""
    console.print(
        f"[bold green]OpenDevOps Dev Server[/bold green] → "
        f"[link=http://{host}:{port}]http://{host}:{port}[/link]  "
        "[dim](reload on)[/dim]"
    )
    uvicorn.run("api.app:app", host=host, port=port, reload=True)
