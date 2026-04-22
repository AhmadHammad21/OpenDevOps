import json
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import print as rprint

from agent.core import InvestigationAgent
from agent.models import Confidence, Investigation

console = Console()

_CONFIDENCE_COLOR = {
    Confidence.HIGH: "green",
    Confidence.MEDIUM: "yellow",
    Confidence.LOW: "red",
}


def investigate_cmd(
    description: Annotated[str, typer.Argument(help="Describe the incident or problem.")],
    alarm: Annotated[str | None, typer.Option("--alarm", "-a", help="CloudWatch alarm name.")] = None,
    service: Annotated[str | None, typer.Option("--service", "-s", help="Service name (e.g. ECS service).")] = None,
    region: Annotated[str | None, typer.Option("--region", "-r", help="AWS region override.")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output raw JSON.")] = False,
) -> None:
    """Investigate an AWS incident and produce a root cause report."""
    investigation = Investigation(description=description, alarm_name=alarm, service=service, region=region)
    agent = InvestigationAgent()

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task("Investigating...", total=None)
        result = agent.investigate(investigation)

    if json_output:
        rprint(json.dumps(result.raw_json or result.model_dump(), indent=2))
        return

    color = _CONFIDENCE_COLOR.get(result.confidence, "white")

    console.print()
    console.print(
        Panel(
            f"[bold]{result.root_cause_summary}[/bold]",
            title=f"[bold cyan]Root Cause — {result.root_cause_category.value}[/bold cyan]",
            subtitle=f"Confidence: [{color}]{result.confidence.value}[/{color}] | Tool calls: {result.tool_calls_made}",
            border_style="cyan",
        )
    )

    if result.evidence:
        table = Table(title="Evidence", show_header=False, box=None, padding=(0, 1))
        for item in result.evidence:
            table.add_row("•", item)
        console.print(table)

    if result.mitigation_steps:
        console.print("\n[bold yellow]Mitigation Steps[/bold yellow]")
        for step in result.mitigation_steps:
            console.print(f"  {step}")

    if result.validation_steps:
        console.print("\n[bold blue]Validation Steps[/bold blue]")
        for step in result.validation_steps:
            console.print(f"  • {step}")

    if result.services_affected:
        console.print(f"\n[bold]Services affected:[/bold] {', '.join(result.services_affected)}")

    if result.recommended_follow_up:
        console.print(
            Panel(result.recommended_follow_up, title="Recommended Follow-up", border_style="dim")
        )
    console.print()
