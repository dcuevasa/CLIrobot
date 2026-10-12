"""Interactive keyboard diagnostics and latency test tool."""

import sys
import time
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from clirobot.ui.console import console, print_info, print_success, print_warning
from clirobot.keyboard.listener import KeyboardManager


def run_keyboard_test() -> None:
    """Launch interactive keyboard testing bench."""
    console.print("\n[bold cyan]⚡ CLIrobot Keyboard Diagnostics & Latency Tester[/bold cyan]")
    console.print("[dim]Press any key to test raw input capture, escape sequences, and response latency.[/dim]")
    console.print("[yellow]Press 'q' or 'ctrl_c' to exit the tester.[/yellow]\n")

    events_log: list[tuple[str, float]] = []
    start_time = time.time()

    def on_key(key: str) -> None:
        events_log.append((key, time.time() - start_time))
        if len(events_log) > 12:
            events_log.pop(0)

    mgr = KeyboardManager(on_action=on_key)
    supported = mgr.start()

    if not supported:
        print_warning("Terminal raw mode is not supported in the current environment (non-TTY stdin).")
        return

    try:
        with Live(console=console, refresh_per_second=15) as live:
            while not mgr.stop_requested:
                table = Table(title="Live Key Log", border_style="bright_blue")
                table.add_column("Key Name", style="bold green", width=16)
                table.add_column("Type", style="cyan", width=14)
                table.add_column("Timestamp", style="dim", width=12)

                for k, t in reversed(events_log):
                    k_type = "Special Key" if len(k) > 1 else "Character"
                    table.add_row(k, k_type, f"+{t:.2f}s")

                panel = Panel(
                    table,
                    title="[bold yellow]Interactive Input Bench — Press Keys to Test[/bold yellow]",
                    subtitle="[dim]Press [bold red]q[/bold red] to return to CLI[/dim]",
                    border_style="cyan",
                )
                live.update(panel)
                time.sleep(0.05)
    finally:
        mgr.stop()
        console.print("\n[bold green]✔ Keyboard diagnostics finished. Terminal restored cleanly.[/bold green]\n")
