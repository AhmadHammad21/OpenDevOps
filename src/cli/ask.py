from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Annotated

import typer
from langchain_litellm import ChatLiteLLM
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
    model = ChatLiteLLM(
        model=settings.llm_model,
        api_base=settings.llm_api_base or None,
        api_key=settings.llm_api_key or None,
    )

    messages = [
        SystemMessage(content=(
            "You are an expert AWS SRE. Answer concisely. If you need specific AWS data to answer "
            "accurately, say so — don't make up metrics or resource names."
        )),
        HumanMessage(content=question),
    ]

    try:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
            progress.add_task("Thinking...", total=None)
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(model.invoke, messages)
                response = future.result(timeout=settings.investigation_timeout)
    except FuturesTimeoutError:
        console.print(
            f"[red]Request timed out after {settings.investigation_timeout}s. Try narrowing the question scope.[/red]"
        )
        raise typer.Exit(code=1)

    console.print(Markdown(response.content))
