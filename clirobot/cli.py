"""Main CLI entrypoint for CLIrobot."""

import sys
from typing import Optional, List
import typer
from rich.panel import Panel
from clirobot import __version__
from clirobot.ui.console import console
from clirobot.ui.banner import print_banner
from clirobot.config.manager import ConfigManager
from clirobot.integration.runner import CommandRunner
from clirobot.integration.commands.ports_cmd import app as ports_app
from clirobot.integration.commands.cameras_cmd import app as cameras_app
from clirobot.integration.commands.calibrate_cmd import app as calibrate_app
from clirobot.integration.commands.teleop_cmd import app as teleop_app
from clirobot.integration.commands.record_cmd import app as record_app
from clirobot.integration.commands.replay_cmd import app as replay_app
from clirobot.integration.commands.train_cmd import app as train_app
from clirobot.integration.commands.eval_cmd import eval_app, rollout_app
from clirobot.integration.commands.motors_cmd import motors_app, joint_limits_app, can_app
from clirobot.integration.commands.dataset_cmd import app as dataset_app
from clirobot.integration.commands.misc_cmd import info_app, annotate_app, tokenizer_app, convert_app
from clirobot.integration.commands.profile_cmd import profile_app, config_app
from clirobot.plugins.cli_cmd import app as plugin_app
from clirobot.plugins.manager import PluginManager
from clirobot.keyboard.tester import run_keyboard_test
from clirobot.doctor.checker import display_doctor_report

app = typer.Typer(
    name="clirobot",
    help="⚡ CLIrobot: Unified Ergonomic Control Hub for Hugging Face LeRobot ⚡",
    add_completion=True,
    no_args_is_help=False,
)

# Register command groups
app.add_typer(ports_app, name="ports", help="Discover and assign USB serial ports for robot arms")
app.add_typer(ports_app, name="find-port", help="Alias for 'ports find'")
app.add_typer(cameras_app, name="cameras", help="Scan, preview, and assign camera roles")
app.add_typer(cameras_app, name="find-cameras", help="Alias for 'cameras scan'")
app.add_typer(calibrate_app, name="calibrate", help="Calibrate robot arms and manage calibration files")
app.add_typer(calibrate_app, name="calibration", help="Alias for calibration file management")
app.add_typer(teleop_app, name="teleop", help="Live teleoperation between leader and follower arms")
app.add_typer(teleop_app, name="teleoperate", help="Alias for 'teleop'")
app.add_typer(record_app, name="record", help="Record dataset demonstrations with robust keyboard hotkeys")
app.add_typer(replay_app, name="replay", help="Replay recorded episodes on the physical robot")
app.add_typer(train_app, name="train", help="Train imitation learning policies (ACT, Diffusion, SmolVLM)")
app.add_typer(eval_app, name="eval", help="Evaluate trained policies on physical robot or in simulation")
app.add_typer(rollout_app, name="rollout", help="Execute policy rollouts")
app.add_typer(motors_app, name="motors", help="Configure servo motor IDs, baudrates, and bus registers")
app.add_typer(motors_app, name="setup-motors", help="Alias for 'motors setup'")
app.add_typer(joint_limits_app, name="joint-limits", help="Find physical min/max joint limits")
app.add_typer(joint_limits_app, name="find-joint-limits", help="Alias for 'joint-limits'")
app.add_typer(can_app, name="can", help="Configure CAN bus interfaces")
app.add_typer(can_app, name="setup-can", help="Alias for 'can setup'")
app.add_typer(dataset_app, name="dataset", help="Visualize, edit, transform, and build sidecars for datasets")
app.add_typer(annotate_app, name="annotate", help="Annotate dataset episodes with language descriptions")
app.add_typer(info_app, name="info", help="Display robot hardware environment and metadata")
app.add_typer(tokenizer_app, name="tokenizer", help="Train action/vision tokenizers")
app.add_typer(convert_app, name="convert", help="Convert PyTorch distributed checkpoints (DCP)")
app.add_typer(profile_app, name="profile", help="Manage and switch robot hardware profiles")
app.add_typer(config_app, name="config", help="Manage global configuration settings")
app.add_typer(plugin_app, name="plugin", help="Manage and inspect CLIrobot plugins")
app.add_typer(plugin_app, name="plugins", help="Alias for 'plugin'")

# Dynamic CLI injection from enabled plugins
_sub_apps = {
    "ports": ports_app,
    "cameras": cameras_app,
    "calibrate": calibrate_app,
    "teleop": teleop_app,
    "record": record_app,
    "replay": replay_app,
    "train": train_app,
    "eval": eval_app,
    "dataset": dataset_app,
    "profile": profile_app,
    "config": config_app,
}

try:
    _pm = PluginManager()
    for _plugin in _pm.list_plugins(enabled_only=True):
        try:
            _plugin.register_cli(app, _sub_apps)
        except Exception:
            pass
except Exception:
    pass


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show CLIrobot version"),
    banner: bool = typer.Option(False, "--banner", help="Print CLIrobot ASCII banner"),
):
    """Main callback: launches interactive TUI if no subcommand passed, or handles global flags."""
    if version:
        console.print(f"[bold cyan]CLIrobot[/bold cyan] version [bold green]{__version__}[/bold green]")
        raise typer.Exit()

    if banner:
        mgr = ConfigManager()
        profile = mgr.get_active_profile()
        print_banner(console, active_profile=profile.name)
        console.print("[dim]Run [bold cyan]clirobot --help[/bold cyan] to see all available commands, or [bold cyan]clirobot doctor[/bold cyan] for diagnostics.[/dim]\n")
        raise typer.Exit()

    # If no subcommand passed, launch interactive TUI menu!
    if ctx.invoked_subcommand is None:
        if not sys.stdin.isatty():
            mgr = ConfigManager()
            profile = mgr.get_active_profile()
            print_banner(console, active_profile=profile.name)
            console.print("[dim]Run [bold cyan]clirobot --help[/bold cyan] to see all available commands.[/dim]\n")
            raise typer.Exit()

        from clirobot.tui.app import TUIApp
        app_instance = TUIApp()
        app_instance.start()
        raise typer.Exit()


@app.command("tui")
@app.command("menu")
def open_tui():
    """Launch the interactive TUI navigation menu."""
    from clirobot.tui.app import TUIApp
    app_instance = TUIApp()
    app_instance.start()


@app.command("doctor")
def run_doctor():
    """Run full system diagnostics and hardware health check."""
    display_doctor_report()



keyboard_app = typer.Typer(help="Keyboard input diagnostics and latency testing.", no_args_is_help=False)


@keyboard_app.callback(invoke_without_command=True)
def default_keyboard_action(ctx: typer.Context):
    """Launch keyboard test when run without subcommand."""
    if ctx.invoked_subcommand is None:
        run_keyboard_test()


@keyboard_app.command("test")
def test_keyboard():
    """Launch interactive keyboard testing bench."""
    run_keyboard_test()


app.add_typer(keyboard_app, name="keyboard", help="Test and diagnose keyboard input responsiveness")


@app.command("run", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def generic_run(
    ctx: typer.Context,
    command: str = typer.Argument(..., help="LeRobot command name (e.g. record, teleoperate, train)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
):
    """Run any underlying LeRobot command with automatic profile settings injection."""
    mgr = ConfigManager()
    runner = CommandRunner(mgr)
    exit_code = runner.run(command, ctx.args, dry_run=dry_run)
    raise typer.Exit(code=exit_code)


def main():
    """Application entrypoint."""
    app()


if __name__ == "__main__":
    main()
