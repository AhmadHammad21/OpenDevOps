from datetime import UTC, datetime

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from tools.cloudwatch import GetAlarmsTool

console = Console()


def report_cmd(
    region: str = typer.Option(None, "--region", "-r", help="AWS region override."),
) -> None:
    """Generate a daily ops health summary: alarm states and error rates."""
    console.print(Panel("[bold cyan]OpenDevOps Agent — Daily Health Report[/bold cyan]", border_style="cyan"))
    console.print(f"[dim]Generated at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}[/dim]\n")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task("Fetching alarm states...", total=None)
        alarms_tool = GetAlarmsTool()
        all_alarms = alarms_tool.run()
        alarm_alarms = alarms_tool.run(state="ALARM")
        insuf_alarms = alarms_tool.run(state="INSUFFICIENT_DATA")

    total = all_alarms.get("count", 0)
    firing = alarm_alarms.get("count", 0)
    insuf = insuf_alarms.get("count", 0)
    ok = total - firing - insuf

    summary_table = Table(show_header=True, header_style="bold")
    summary_table.add_column("Status", style="bold")
    summary_table.add_column("Count", justify="right")
    summary_table.add_row("[green]OK[/green]", str(ok))
    summary_table.add_row("[red]ALARM[/red]", str(firing))
    summary_table.add_row("[yellow]INSUFFICIENT_DATA[/yellow]", str(insuf))
    summary_table.add_row("Total", str(total))
    console.print(summary_table)

    if alarm_alarms.get("alarms"):
        console.print("\n[bold red]Firing Alarms[/bold red]")
        firing_table = Table(show_header=True, header_style="bold red")
        firing_table.add_column("Alarm Name")
        firing_table.add_column("Metric")
        firing_table.add_column("Reason")
        for alarm in alarm_alarms["alarms"]:
            firing_table.add_row(alarm["name"], alarm.get("metric", ""), alarm.get("reason", "")[:80])
        console.print(firing_table)

    console.print("\n[dim]Run `devops-agent investigate \"<description>\"` to investigate a specific alarm.[/dim]\n")
