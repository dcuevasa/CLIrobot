"""Interactive arrow-key navigable TUI menu renderer and event loop."""

import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Sequence
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from clirobot.ui.console import console
from clirobot.ui.banner import BANNER_ART, SLOGAN
from clirobot.keyboard.terminal import read_key, is_keyboard_supported
from clirobot.config.schema import RobotProfile


@dataclass
class MenuItem:
    """An interactive menu item with icon, label, description, and action id."""
    id: str
    label: str
    icon: str = "•"
    description: str = ""
    badge: str | None = None
    metadata: Any = None


def clear_terminal() -> None:
    """Clear terminal screen cross-platform."""
    if sys.platform.startswith("win"):
        os.system("cls")
    else:
        # Fast ANSI clear screen and home cursor
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def render_menu_screen(
    title: str,
    subtitle: str,
    items: list[MenuItem],
    selected_index: int,
    active_profile: RobotProfile | None = None,
    breadcrumbs: list[str] | None = None,
) -> None:
    """Render full TUI menu frame with active profile header, item list, and help bar."""
    clear_terminal()

    # 1. Header Banner & Profile Status
    header_text = Text()
    header_text.append(BANNER_ART.strip("\n"), style="bold cyan")
    header_text.append("\n")
    header_text.append(f"{SLOGAN}\n", style="bold yellow")

    status_line = Text()
    if active_profile:
        leader_p = active_profile.leader_arm.port or "Not Set"
        follower_p = active_profile.follower_arm.port or "Not Set"
        cams_count = len(active_profile.cameras)
        status_line.append("Profile: ", style="dim")
        status_line.append(f"{active_profile.name}", style="bold green")
        status_line.append(f" ({active_profile.robot_type})  |  ", style="dim")
        status_line.append("Leader: ", style="dim")
        status_line.append(f"{leader_p}", style="bold cyan")
        status_line.append("  |  Follower: ", style="dim")
        status_line.append(f"{follower_p}", style="bold cyan")
        status_line.append(f"  |  Cameras: [bold]{cams_count}[/bold]", style="dim")

    console.print(
        Panel(
            Align.center(header_text),
            subtitle=status_line,
            border_style="bright_blue",
            padding=(0, 2),
        )
    )

    # 2. Breadcrumbs & Section Title
    path_str = " ❯ ".join(breadcrumbs or [title])
    console.print(f"[bold magenta]📍 {path_str}[/bold magenta]")
    if subtitle:
        console.print(f"[dim]{subtitle}[/dim]\n")
    else:
        console.print()

    # 3. Interactive Items List
    menu_table = Table.grid(padding=(0, 2))
    menu_table.add_column(width=4, justify="right")   # Cursor
    menu_table.add_column(width=4, justify="center")  # Icon
    menu_table.add_column(style="white", width=34)    # Label
    menu_table.add_column(style="dim")                # Badge / info

    for i, item in enumerate(items):
        is_selected = (i == selected_index)

        if is_selected:
            cursor = "[bold yellow]❯[/bold yellow]"
            icon_str = f"[bold yellow]{item.icon}[/bold yellow]"
            label_str = f"[bold black on cyan] {item.label} [/bold black on cyan]"
            badge_str = f"[bold green]{item.badge}[/bold green]" if item.badge else ""
        else:
            cursor = " "
            icon_str = f"[cyan]{item.icon}[/cyan]"
            label_str = f"[white]{item.label}[/white]"
            badge_str = f"[dim]{item.badge}[/dim]" if item.badge else ""

        menu_table.add_row(cursor, icon_str, label_str, badge_str)

    console.print(Panel(menu_table, border_style="dim", padding=(1, 2)))

    # 4. Description Box for Selected Item
    selected_item = items[selected_index] if 0 <= selected_index < len(items) else None
    if selected_item and selected_item.description:
        desc_panel = Panel(
            f"[cyan]{selected_item.description}[/cyan]",
            title="[bold yellow]Information[/bold yellow]",
            border_style="yellow",
            padding=(0, 2),
        )
        console.print(desc_panel)

    # 5. Bottom Navigation Bar
    console.print(
        Align.center(
            "[dim]Navigation: [/dim]"
            "[bold cyan][↑/↓][/bold cyan] Move Selection  •  "
            "[bold cyan][Enter][/bold cyan] Select  •  "
            "[bold cyan][Esc/b][/bold cyan] Back  •  "
            "[bold cyan][q][/bold cyan] Exit TUI"
        )
    )


def run_menu(
    title: str,
    subtitle: str,
    items: list[MenuItem],
    active_profile: RobotProfile | None = None,
    breadcrumbs: list[str] | None = None,
    initial_index: int = 0,
) -> MenuItem | None:
    """Run an interactive arrow-key selection loop.
    
    Returns:
        Selected MenuItem, or None if user pressed Esc/back or 'q'.
    """
    if not items:
        return None

    if not is_keyboard_supported():
        # Fallback to simple number selection if non-interactive environment
        return _fallback_number_selection(title, subtitle, items)

    selected_index = max(0, min(initial_index, len(items) - 1))

    while True:
        render_menu_screen(
            title=title,
            subtitle=subtitle,
            items=items,
            selected_index=selected_index,
            active_profile=active_profile,
            breadcrumbs=breadcrumbs,
        )

        key = read_key(timeout=None)
        if not key:
            continue

        if key in ("up", "k"):
            selected_index = (selected_index - 1) % len(items)
        elif key in ("down", "j"):
            selected_index = (selected_index + 1) % len(items)
        elif key in ("enter", "space"):
            return items[selected_index]
        elif key in ("esc", "b", "left"):
            return None
        elif key in ("q", "ctrl_c"):
            clear_terminal()
            console.print("[yellow]Exited CLIrobot TUI.[/yellow]\n")
            sys.exit(0)


def _fallback_number_selection(
    title: str,
    subtitle: str,
    items: list[MenuItem],
) -> MenuItem | None:
    """Fallback numbered choice selection for non-TTY or piping."""
    from rich.prompt import Prompt
    console.print(f"\n[bold cyan]{title}[/bold cyan]: {subtitle}")
    for idx, itm in enumerate(items, 1):
        console.print(f"  [{idx}] {itm.icon} {itm.label} [dim]({itm.description})[/dim]")
    console.print("  [0] Back / Exit")

    choice = Prompt.ask("Select option", default="1").strip()
    if choice == "0":
        return None
    try:
        val = int(choice)
        if 1 <= val <= len(items):
            return items[val - 1]
    except ValueError:
        pass
    return None
