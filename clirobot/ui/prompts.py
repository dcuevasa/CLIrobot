"""Interactive prompts and selection dialogs."""

from typing import Any
from rich.prompt import Prompt, Confirm
from rich.table import Table
from clirobot.ui.console import console


def prompt_select(
    title: str,
    choices: list[str],
    default: str | None = None,
    allow_custom: bool = False,
) -> str:
    """Prompt the user to select an item from a numbered list."""
    if not choices:
        raise ValueError("Cannot prompt selection from empty choices list.")

    table = Table(title=f"[bold cyan]{title}[/bold cyan]", show_header=False, border_style="dim")
    table.add_column("Index", style="bold yellow", width=4)
    table.add_column("Option", style="white")

    for i, choice in enumerate(choices, 1):
        suffix = " [dim](default)[/dim]" if choice == default else ""
        table.add_row(f"[{i}]", f"{choice}{suffix}")

    console.print(table)

    valid_indexes = [str(i) for i in range(1, len(choices) + 1)]
    default_index = str(choices.index(default) + 1) if default in choices else "1"

    while True:
        prompt_text = f"Select [1-{len(choices)}]"
        if allow_custom:
            prompt_text += " or enter custom value"

        response = Prompt.ask(prompt_text, default=default_index).strip()
        if response in valid_indexes:
            return choices[int(response) - 1]
        elif allow_custom and response:
            return response
        else:
            console.print("[yellow]Invalid selection, please try again.[/yellow]")


def prompt_text(question: str, default: str | None = None) -> str:
    """Ask a text question with optional default."""
    if default is not None:
        return Prompt.ask(question, default=default).strip()
    return Prompt.ask(question).strip()


def prompt_confirm(question: str, default: bool = True) -> bool:
    """Ask a yes/no confirmation question."""
    return Confirm.ask(question, default=default)
