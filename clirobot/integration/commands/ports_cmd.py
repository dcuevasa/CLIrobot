"""CLI subcommands for serial port management and discovery."""

import typer
from typing import Optional, List
from clirobot.config.manager import ConfigManager
from clirobot.hardware.ports import get_available_ports, display_ports_table, run_interactive_port_wizard
from clirobot.hardware.udev import generate_udev_rules, print_udev_guide
from clirobot.integration.runner import CommandRunner
from clirobot.ui.console import console, print_success, print_info

app = typer.Typer(help="Manage and discover USB serial ports for robot arms.", no_args_is_help=False)


@app.callback(invoke_without_command=True)
def default_ports_action(ctx: typer.Context):
    """List ports or show help when run without subcommand."""
    if ctx.invoked_subcommand is None:
        list_ports()


@app.command("list")
def list_ports():
    """List all detected USB serial ports and active profile assignments."""
    mgr = ConfigManager()
    profile = mgr.get_active_profile()
    ports = get_available_ports(profile.leader_arm.port, profile.follower_arm.port)
    display_ports_table(ports)


@app.command("find")
def find_ports(
    wizard: bool = typer.Option(True, "--wizard/--raw", help="Launch interactive wizard or raw lerobot-find-port"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Find robot arm ports and optionally save them to the active profile."""
    mgr = ConfigManager()
    if wizard:
        run_interactive_port_wizard(mgr)
    else:
        runner = CommandRunner(mgr)
        runner.run("find-port", extra or [], dry_run=dry_run)


@app.command("assign")
def assign_port(
    leader: Optional[str] = typer.Option(None, "--leader", "-l", help="Port path for Leader arm (e.g. /dev/ttyACM0)"),
    follower: Optional[str] = typer.Option(None, "--follower", "-f", help="Port path for Follower arm (e.g. /dev/ttyACM1)"),
):
    """Assign specific port paths to Leader and/or Follower arm in active profile."""
    mgr = ConfigManager()
    profile = mgr.get_active_profile()

    if not leader and not follower:
        print_info("No ports specified. Use --leader or --follower, or run 'clirobot ports find' for interactive setup.")
        return

    mgr.update_ports(leader_port=leader, follower_port=follower)
    print_success(f"Updated profile '[bold green]{profile.name}[/bold green]':")
    if leader:
        console.print(f"  • Leader Port:   [bold cyan]{leader}[/bold cyan]")
    if follower:
        console.print(f"  • Follower Port: [bold cyan]{follower}[/bold cyan]")


@app.command("udev")
def create_udev():
    """Generate Linux udev rules for permanent, predictable arm symlinks."""
    mgr = ConfigManager()
    rules = generate_udev_rules(mgr)
    print_udev_guide(rules)
