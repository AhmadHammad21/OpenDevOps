from typing import Annotated

import typer


def mcp_cmd(
    http: Annotated[bool, typer.Option("--http", help="Use HTTP+SSE transport instead of stdio.")] = False,
    port: Annotated[int, typer.Option("--port", "-p", help="Port for HTTP transport.")] = 8001,
) -> None:
    """Start the MCP server (stdio for Claude Desktop, --http for remote clients)."""
    from mcp_server import run_http, run_stdio
    if http:
        typer.echo(f"Starting MCP server on http://0.0.0.0:{port}/sse")
        run_http(port=port)
    else:
        run_stdio()
