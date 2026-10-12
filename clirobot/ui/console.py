"""Console management and Rich output formatting utilities."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme
from rich.style import Style

# Custom themed styles for robotics CLI
ROBOT_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "danger": "bold red",
    "success": "bold green",
    "step": "bold magenta",
    "hardware": "bold blue",
    "highlight": "bold underline",
    "muted": "dim white",
})

console = Console(theme=ROBOT_THEME)
err_console = Console(theme=ROBOT_THEME, stderr=True)


def print_step(msg: str, step_num: int | None = None) -> None:
    """Print an action step with styled badge."""
    prefix = f"[step]▶ Step {step_num}[/step]" if step_num is not None else "[step]▶[/step]"
    console.print(f"{prefix} {msg}")


def print_success(msg: str) -> None:
    """Print a success confirmation."""
    console.print(f"[success]✔[/success] {msg}")


def print_warning(msg: str) -> None:
    """Print a warning message."""
    console.print(f"[warning]⚠[/warning] {msg}")


def print_error(msg: str) -> None:
    """Print an error message."""
    err_console.print(f"[danger]✘[/danger] {msg}")


def print_info(msg: str) -> None:
    """Print an info notice."""
    console.print(f"[info]ℹ[/info] {msg}")


def print_hardware(msg: str) -> None:
    """Print a hardware-specific event."""
    console.print(f"[hardware]⚙[/hardware] {msg}")


def create_table(title: str, columns: list[str]) -> Table:
    """Create a styled Rich table."""
    table = Table(
        title=f"[bold cyan]{title}[/bold cyan]",
        header_style="bold magenta",
        border_style="bright_blue",
        title_justify="left",
    )
    for col in columns:
        table.add_column(col)
    return table


def make_card(title: str, content: str, style: str = "bright_blue") -> Panel:
    """Create a styled panel card."""
    return Panel(content, title=f"[bold]{title}[/bold]", border_style=style, padding=(1, 2))
