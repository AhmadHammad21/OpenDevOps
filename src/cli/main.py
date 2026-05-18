import sys

import typer
from loguru import logger
from rich.console import Console

from config import settings

app = typer.Typer(
    name="devops-agent",
    help="OpenDevOps Agent — open-source AWS incident investigation powered by OpenRouter LLMs.",
    no_args_is_help=True,
)
console = Console()


def _setup_logging() -> None:
    logger.remove()
    if settings.log_console_enabled:
        logger.add(
            sys.stderr,
            level=settings.log_level.upper(),
            colorize=settings.log_console_colorize,
        )


@app.callback()
def main() -> None:
    _setup_logging()


# Import sub-commands so they register on the app
from cli.investigate import investigate_cmd  # noqa: E402
from cli.ask import ask_cmd  # noqa: E402
from cli.report import report_cmd  # noqa: E402
from cli.ui import ui_cmd  # noqa: E402
from cli.mcp import mcp_cmd  # noqa: E402
from cli.dev import dev_cmd  # noqa: E402
from cli.migrate import migrate_cmd  # noqa: E402

app.command("investigate")(investigate_cmd)
app.command("ask")(ask_cmd)
app.command("report")(report_cmd)
app.command("ui")(ui_cmd)
app.command("mcp")(mcp_cmd)
app.command("dev")(dev_cmd)
app.command("migrate")(migrate_cmd)
