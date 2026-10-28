"""CLI commands for managing CLIrobot plugins."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
import typer
from rich.panel import Panel
from rich.table import Table

from clirobot.config.manager import ConfigManager
from clirobot.plugins.base import DatasetTransformPlugin, RuntimeMiddlewarePlugin, ServicePlugin
from clirobot.plugins.manager import PluginManager
from clirobot.ui.console import console, create_table, print_error, print_info, print_success, print_warning

app = typer.Typer(help="Manage and inspect CLIrobot plugins.", no_args_is_help=False)


@app.command("list")
def list_plugins():
    """List all discovered plugins and their availability."""
    mgr = ConfigManager()
    pm = PluginManager(mgr)
    plugins = pm.list_plugins()

    table = create_table(
        "Discovered Plugins",
        ["ID", "Name", "Category", "Status", "Capabilities", "Version"],
    )

    for p in plugins:
        is_enabled = mgr.is_plugin_enabled(p.metadata.id)
        is_avail, reason = p.is_available()

        if not is_avail:
            status = f"[bold red]UNAVAILABLE[/bold red] ({reason})"
        elif is_enabled:
            status = "[bold green]ENABLED[/bold green]"
        else:
            status = "[bold yellow]DISABLED[/bold yellow]"

        caps = []
        if isinstance(p, DatasetTransformPlugin):
            caps.append("Transforms")
        if isinstance(p, RuntimeMiddlewarePlugin):
            caps.append("Middleware")
        if isinstance(p, ServicePlugin):
            caps.append("Service")
        cap_str = ", ".join(caps) if caps else "General"

        table.add_row(
            f"[bold cyan]{p.metadata.id}[/bold cyan]",
            p.metadata.name,
            p.metadata.category,
            status,
            cap_str,
            p.metadata.version,
        )

    console.print(table)
    console.print("[dim]Use 'clirobot plugin info <id>' for detailed capabilities.[/dim]\n")


@app.command("info")
def plugin_info(
    plugin_id: str = typer.Argument(..., help="Plugin ID to inspect"),
):
    """Display detailed capabilities and configuration for a plugin."""
    mgr = ConfigManager()
    pm = PluginManager(mgr)
    plugin = pm.get_plugin(plugin_id)

    if not plugin:
        print_error(f"Plugin '{plugin_id}' not found. Run 'clirobot plugin list'.")
        raise typer.Exit(code=1)

    meta = plugin.metadata
    is_enabled = mgr.is_plugin_enabled(plugin_id)
    is_avail, reason = plugin.is_available()

    info_lines = [
        f"[bold cyan]ID:[/bold cyan]          {meta.id}",
        f"[bold cyan]Name:[/bold cyan]        {meta.name}",
        f"[bold cyan]Version:[/bold cyan]     {meta.version}",
        f"[bold cyan]Category:[/bold cyan]    {meta.category}",
        f"[bold cyan]Author:[/bold cyan]      {meta.author or 'N/A'}",
        f"[bold cyan]Status:[/bold cyan]      {'[green]Enabled[/green]' if is_enabled else '[yellow]Disabled[/yellow]'} ({reason})",
        f"[bold cyan]Description:[/bold cyan] {meta.description}",
    ]

    if isinstance(plugin, DatasetTransformPlugin):
        transforms = plugin.get_transforms()
        info_lines.append(f"\n[bold green]Dataset Transforms ({len(transforms)}):[/bold green]")
        for t in transforms:
            info_lines.append(f"  • {t.icon} [bold]{t.id}[/bold]: {t.description}")

    if isinstance(plugin, RuntimeMiddlewarePlugin):
        cmds = plugin.applies_to_commands()
        info_lines.append(f"\n[bold green]Runtime Middleware Hooks:[/bold green] {', '.join(cmds)}")

    if isinstance(plugin, ServicePlugin):
        info_lines.append("\n[bold green]Service Plugin:[/bold green] Exposes daemon/web endpoints.")

    # Show active profile configuration
    cfg = mgr.get_plugin_config(plugin_id)
    info_lines.append(f"\n[bold green]Active Profile Config ({mgr.get_active_profile().name}):[/bold green]")
    info_lines.append(json.dumps(cfg, indent=2))

    console.print(
        Panel(
            "\n".join(info_lines),
            title=f"[bold blue]🧩 Plugin: {meta.name}[/bold blue]",
            border_style="bright_blue",
            padding=(1, 2),
        )
    )


@app.command("enable")
def enable_plugin(
    plugin_id: str = typer.Argument(..., help="Plugin ID to enable"),
):
    """Enable a plugin globally."""
    mgr = ConfigManager()
    mgr.enable_plugin(plugin_id)
    print_success(f"Plugin '[bold green]{plugin_id}[/bold green]' is now enabled.")


@app.command("disable")
def disable_plugin(
    plugin_id: str = typer.Argument(..., help="Plugin ID to disable"),
):
    """Disable a plugin globally."""
    mgr = ConfigManager()
    mgr.disable_plugin(plugin_id)
    print_warning(f"Plugin '[bold yellow]{plugin_id}[/bold yellow]' is now disabled.")


@app.command("add")
def add_plugin_path(
    path: str = typer.Argument(..., help="Directory path to search for plugins"),
):
    """Add a directory to the plugin search paths."""
    mgr = ConfigManager()
    p = Path(path).expanduser().resolve()
    if not p.is_dir():
        print_error(f"Path does not exist or is not a directory: {p}")
        raise typer.Exit(code=1)

    if mgr.add_plugin_search_path(str(p)):
        print_success(f"Added plugin search path: {p}")
    else:
        print_info(f"Path already registered: {p}")
