from typing import Annotated

import typer
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from rich.console import Console
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn

from agent.config import settings

console = Console()


def ask_cmd(
    question: Annotated[str, typer.Argument(help="Freeform question about your AWS environment.")],
) -> None:
    """Ask a freeform question about your AWS environment."""
    model = ChatOpenAI(
        model=settings.openrouter_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )

    messages = [
        SystemMessage(content=(
            "You are an expert AWS SRE. Answer concisely. If you need specific AWS data to answer "
            "accurately, say so — don't make up metrics or resource names."
        )),
        HumanMessage(content=question),
    ]

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task("Thinking...", total=None)
        response = model.invoke(messages)

    console.print(Markdown(response.content))
