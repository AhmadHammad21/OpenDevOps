import sys
from typing import Annotated

import typer
import uvicorn
from rich.console import Console

# psycopg3 async requires SelectorEventLoop on Windows (ProactorEventLoop is the default)
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

console = Console()


def ui_cmd(
    host: Annotated[str, typer.Option("--host", help="Bind host.")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", "-p", help="Port to listen on.")] = 8000,
) -> None:
    """Launch the web UI chat interface."""
    console.print(f"[bold cyan]OpenDevOps Agent UI[/bold cyan] → [link=http://{host}:{port}]http://{host}:{port}[/link]")
    uvicorn.run("api.app:app", host=host, port=port, reload=False)
