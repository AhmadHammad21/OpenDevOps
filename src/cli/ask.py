from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn

from agent.config import settings
from openai import OpenAI

console = Console()


def ask_cmd(
    question: Annotated[str, typer.Argument(help="Freeform question about your AWS environment.")],
) -> None:
    """Ask a freeform question about your AWS environment."""
    client = OpenAI(api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url)

    system = (
        "You are an expert AWS SRE. Answer concisely. If you need specific AWS data to answer "
        "accurately, say so — don't make up metrics or resource names."
    )

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task("Thinking...", total=None)
        response = client.chat.completions.create(
            model=settings.openrouter_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": question},
            ],
        )

    answer = response.choices[0].message.content or ""
    console.print(Markdown(answer))
