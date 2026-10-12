"""CLI subcommands for managing robot profiles and global settings."""

import json
from pathlib import Path
from typing import Optional
import typer
from rich.panel import Panel
from rich.table import Table
from clirobot.config.manager import ConfigManager
from clirobot.config.schema import RobotProfile
from clirobot.constants import SUPPORTED_ROBOTS
from clirobot.ui.console import console, print_success, print_info, print_warning, print_error, create_table
from clirobot.ui.prompts import prompt_select, prompt_text, prompt_confirm

profile_app = typer.Typer(help="Manage robot hardware profiles (arms, ports, cameras).", no_args_is_help=False)
config_app = typer.Typer(help="Configure global CLIrobot settings.", no_args_is_help=False)


@profile_app.callback(invoke_without_command=True)
def default_profile_action(ctx: typer.Context):
    """List profiles when run without subcommand."""
    if ctx.invoked_subcommand is None:
        list_profiles()


@profile_app.command("list")
def list_profiles():
    """List all saved profiles and their configurations."""
    mgr = ConfigManager()
    cfg = mgr.config

    table = create_table("Robot Hardware Profiles", ["Active", "Profile Name", "Robot Type", "Leader Port", "Follower Port", "Cameras"])

    for name, p in cfg.profiles.items():
        is_active = "[bold green]▶ ACTIVE[/bold green]" if name == cfg.active_profile else ""
        cams_count = f"{len(p.cameras)} camera(s)" if p.cameras else "[dim]None[/dim]"
        leader_p = p.leader_arm.port if p.leader_arm and p.leader_arm.port else "[dim]Not set[/dim]"
        follower_p = p.follower_arm.port if p.follower_arm and p.follower_arm.port else "[dim]Not set[/dim]"

        table.add_row(
            is_active,
            f"[bold cyan]{name}[/bold cyan]",
            p.robot_type,
            leader_p,
            follower_p,
            cams_count,
        )

    console.print(table)


@profile_app.command("switch")
def switch_profile(name: str = typer.Argument(..., help="Name of profile to activate")):
    """Switch the currently active profile."""
    mgr = ConfigManager()
    if mgr.set_active_profile(name):
        print_success(f"Switched active profile to: [bold green]{name}[/bold green]")
    else:
        print_error(f"Profile '{name}' does not exist. Available profiles: {', '.join(mgr.list_profiles())}")


@profile_app.command("create")
def create_profile(
    name: str = typer.Argument(..., help="Name for the new profile"),
    robot_type: str = typer.Option("so100", "--robot-type", "-r", help="Robot type (so100, koch, aloha, etc.)"),
    clone_from: Optional[str] = typer.Option(None, "--clone-from", "-c", help="Clone settings from existing profile"),
    notes: str = typer.Option("", "--notes", help="Optional description/notes"),
):
    """Create a new robot profile."""
    mgr = ConfigManager()
    if name in mgr.config.profiles:
        print_error(f"Profile '{name}' already exists.")
        return

    profile = mgr.create_profile(name=name, robot_type=robot_type, clone_from=clone_from, notes=notes)
    print_success(f"Created profile '[bold green]{name}[/bold green]' (type: {profile.robot_type}).")
    if prompt_confirm(f"Set '{name}' as the active profile?", default=True):
        mgr.set_active_profile(name)
        print_success(f"Active profile set to '{name}'.")


@profile_app.command("delete")
def delete_profile(name: str = typer.Argument(..., help="Name of profile to delete")):
    """Delete a profile."""
    mgr = ConfigManager()
    if name not in mgr.config.profiles:
        print_error(f"Profile '{name}' not found.")
        return

    if len(mgr.config.profiles) <= 1:
        print_error("Cannot delete the only remaining profile.")
        return

    if prompt_confirm(f"Are you sure you want to delete profile '{name}'?", default=False):
        mgr.delete_profile(name)
        print_success(f"Deleted profile '{name}'. Active profile is now '{mgr.config.active_profile}'.")


@profile_app.command("show")
def show_profile(name: Optional[str] = typer.Argument(None, help="Profile name (defaults to active profile)")):
    """Inspect complete settings of a profile."""
    mgr = ConfigManager()
    profile = mgr.config.profiles.get(name) if name else mgr.get_active_profile()

    if not profile:
        print_error(f"Profile '{name}' not found.")
        return

    content = Table.grid(padding=(0, 2))
    content.add_column(style="bold cyan", width=18)
    content.add_column(style="white")

    content.add_row("Profile Name:", profile.name)
    content.add_row("Robot Type:", profile.robot_type)
    content.add_row("Teleop Type:", profile.teleop_type)
    content.add_row("Leader Port:", profile.leader_arm.port or "[dim]Not configured[/dim]")
    content.add_row("Follower Port:", profile.follower_arm.port or "[dim]Not configured[/dim]")
    content.add_row("Dataset Repo:", profile.dataset_repo_id)
    content.add_row("Default FPS:", str(profile.default_fps))
    content.add_row("Notes:", profile.notes or "[dim]None[/dim]")

    if profile.cameras:
        cams_str = ", ".join([f"{k} (id: {c.index_or_path})" for k, c in profile.cameras.items()])
        content.add_row("Cameras:", cams_str)
    else:
        content.add_row("Cameras:", "[dim]No cameras configured[/dim]")

    console.print(Panel(content, title=f"[bold green]Profile: {profile.name}[/bold green]", border_style="bright_blue"))


@profile_app.command("export")
def export_profile(
    name: str = typer.Argument(..., help="Profile name to export"),
    dest: Path = typer.Argument(..., help="Target file path"),
):
    """Export a profile to JSON file."""
    mgr = ConfigManager()
    profile = mgr.config.profiles.get(name)
    if not profile:
        print_error(f"Profile '{name}' not found.")
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(profile.to_dict(), f, indent=2)
    print_success(f"Exported profile '{name}' to [bold cyan]{dest}[/bold cyan]")


@profile_app.command("import")
def import_profile(src: Path = typer.Argument(..., help="Source JSON file path")):
    """Import a profile from JSON file."""
    if not src.exists():
        print_error(f"Source file {src} not found.")
        return

    with open(src, "r", encoding="utf-8") as f:
        data = json.load(f)

    profile = RobotProfile.from_dict(data)
    mgr = ConfigManager()
    mgr.config.profiles[profile.name] = profile
    mgr.save()
    print_success(f"Imported profile '[bold green]{profile.name}[/bold green]'.")


@config_app.command("show")
def show_config():
    """Display global configuration settings."""
    mgr = ConfigManager()
    cfg = mgr.config

    table = create_table("Global CLIrobot Configuration", ["Setting", "Value"])
    table.add_row("Active Profile", f"[bold green]{cfg.active_profile}[/bold green]")
    table.add_row("LeRobot Executable Path", cfg.lerobot_path or "[dim]System PATH default[/dim]")
    table.add_row("Auto-Save Detected Ports", "[green]True[/green]" if cfg.auto_save_ports else "[yellow]False[/yellow]")
    table.add_row("Default Backend", cfg.default_backend)
    table.add_row("Config File Location", str(mgr.config_path))
    console.print(table)


@config_app.command("set")
def set_config(
    key: str = typer.Argument(..., help="Setting name (lerobot_path, auto_save_ports, default_backend)"),
    value: str = typer.Argument(..., help="Setting value"),
):
    """Update a global configuration setting."""
    mgr = ConfigManager()
    if key == "lerobot_path":
        mgr.config.lerobot_path = value
    elif key == "auto_save_ports":
        mgr.config.auto_save_ports = value.lower() in ("true", "1", "yes")
    elif key == "default_backend":
        mgr.config.default_backend = value
    else:
        print_error(f"Unknown configuration key: {key}")
        return

    mgr.save()
    print_success(f"Updated setting '[bold cyan]{key}[/bold cyan]' -> [green]{value}[/green]")
