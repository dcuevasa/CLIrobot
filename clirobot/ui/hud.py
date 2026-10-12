"""Real-time Heads-Up Display (HUD) for teleoperation and recording sessions."""

import time
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.layout import Layout


def build_hud_panel(
    status: str = "IDLE",
    episode_index: int = 1,
    total_episodes: int = 10,
    fps: float = 30.0,
    current_action: str = "Ready",
    last_key: str | None = None,
    backend: str = "Terminal Raw",
) -> Panel:
    """Build a styled Rich HUD panel showing session metrics and live hotkey state."""
    # Status badge
    if status == "RECORDING":
        status_text = "[bold white on red] ● RECORDING [/bold white on red]"
    elif status == "PAUSED":
        status_text = "[bold black on yellow] ❚❚ PAUSED [/bold black on yellow]"
    elif status == "SAVING":
        status_text = "[bold white on blue] ⟳ SAVING [/bold white on blue]"
    else:
        status_text = f"[bold green]{status}[/bold green]"

    # Key flash badge
    key_badge = f"[bold yellow on black] {last_key.upper()} [/bold yellow on black]" if last_key else "[dim]None[/dim]"

    content = Table.grid(padding=(0, 2))
    content.add_column(style="bold cyan", width=16)
    content.add_column(style="white")

    content.add_row("Session State:", status_text)
    content.add_row("Episode:", f"[bold cyan]{episode_index}[/bold cyan] / [bold]{total_episodes}[/bold]")
    content.add_row("Frequency:", f"[green]{fps:.1f} FPS[/green]")
    content.add_row("Last Key Press:", key_badge)
    content.add_row("Key Backend:", f"[dim]{backend}[/dim]")

    hotkeys_guide = (
        "\n[bold magenta]Controls:[/bold magenta] "
        "[bold cyan][SPACE][/bold cyan] Record/Pause  •  "
        "[bold cyan][R][/bold cyan] Re-record  •  "
        "[bold cyan][N][/bold cyan] Next Episode  •  "
        "[bold cyan][Q][/bold cyan] Quit/Save"
    )

    full_text = Text.from_markup(f"{hotkeys_guide}")

    main_table = Table.grid()
    main_table.add_row(content)
    main_table.add_row(full_text)

    return Panel(
        main_table,
        title="[bold bright_blue]⚡ CLIrobot Teleoperation & Recording HUD ⚡[/bold bright_blue]",
        border_style="bright_blue",
        padding=(1, 2),
    )
