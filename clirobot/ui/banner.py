"""ASCII banners and styling aesthetics for CLIrobot."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align

BANNER_ART = r"""
   ██████╗██╗     ██╗██████╗  ██████╗ ██████╗  ██████╗ ████████╗
  ██╔════╝██║     ██║██╔══██╗██╔═══██╗██╔══██╗██╔═══██╗╚══██╔══╝
  ██║     ██║     ██║██████╔╝██║   ██║██████╔╝██║   ██║   ██║   
  ██║     ██║     ██║██╔══██╗██║   ██║██╔══██╗██║   ██║   ██║   
  ╚██████╗███████╗██║██║  ██║╚██████╔╝██████╔╝╚██████╔╝   ██║   
   ╚═════╝╚══════╝╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝  ╚═════╝    ╚═╝   
"""

SLOGAN = "⚡ Unified Ergonomic Hub for Hugging Face LeRobot ⚡"


def get_banner_panel(active_profile: str | None = None, version: str = "0.1.0") -> Panel:
    """Build a styled Rich panel containing the CLIrobot banner."""
    content = Text()
    content.append(BANNER_ART.strip("\n"), style="bold cyan")
    content.append("\n\n")
    content.append(f"  {SLOGAN}\n", style="bold yellow")
    
    status_line = f"  v{version}"
    if active_profile:
        status_line += f"  •  Active Profile: [bold green]{active_profile}[/bold green]"
    
    return Panel(
        Align.center(content),
        subtitle=status_line,
        border_style="bright_blue",
        padding=(0, 2),
    )


def print_banner(console: Console, active_profile: str | None = None) -> None:
    """Print the CLIrobot banner to the provided console."""
    console.print(get_banner_panel(active_profile))
