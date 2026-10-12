"""CLI subcommands for motor bus setup, calibration of joint limits, and CAN bus."""

import typer
from typing import Optional, List
from clirobot.config.manager import ConfigManager
from clirobot.integration.runner import CommandRunner
from clirobot.ui.console import console

motors_app = typer.Typer(help="Configure motor IDs, baud rates, and bus registers.", no_args_is_help=False)
joint_limits_app = typer.Typer(help="Find and calibrate physical joint travel limits.", no_args_is_help=False)
can_app = typer.Typer(help="Configure CAN bus interfaces for supported robots.", no_args_is_help=False)


@motors_app.callback(invoke_without_command=True)
def setup_motors(
    ctx: typer.Context,
    robot_type: Optional[str] = typer.Option(None, "--robot-type", "-r", help="Robot type (e.g. so100)"),
    port: Optional[str] = typer.Option(None, "--port", "-p", help="Serial port for motors bus"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Run lerobot-setup-motors to assign IDs and test servo motors."""
    mgr = ConfigManager()
    profile = mgr.get_active_profile()

    args = []
    target_type = robot_type or profile.robot_type
    if target_type:
        args.append(f"--robot.type={target_type}")

    target_port = port or (profile.follower_arm.port if profile.follower_arm else "")
    if target_port:
        args.append(f"--robot.port={target_port}")

    if extra:
        args.extend(extra)

    runner = CommandRunner(mgr)
    exit_code = runner.run("setup-motors", args, dry_run=dry_run)
    raise typer.Exit(code=exit_code)


@joint_limits_app.callback(invoke_without_command=True)
def find_joint_limits(
    ctx: typer.Context,
    robot_type: Optional[str] = typer.Option(None, "--robot-type", "-r", help="Robot type"),
    port: Optional[str] = typer.Option(None, "--port", "-p", help="Serial port for motors bus"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Run lerobot-find-joint-limits to discover min and max angular range."""
    mgr = ConfigManager()
    profile = mgr.get_active_profile()

    args = []
    target_type = robot_type or profile.robot_type
    if target_type:
        args.append(f"--robot.type={target_type}")

    target_port = port or (profile.follower_arm.port if profile.follower_arm else "")
    if target_port:
        args.append(f"--robot.port={target_port}")

    if extra:
        args.extend(extra)

    runner = CommandRunner(mgr)
    exit_code = runner.run("find-joint-limits", args, dry_run=dry_run)
    raise typer.Exit(code=exit_code)


@can_app.callback(invoke_without_command=True)
def setup_can(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Run lerobot-setup-can to configure socketcan / slcan interfaces."""
    mgr = ConfigManager()
    runner = CommandRunner(mgr)
    exit_code = runner.run("setup-can", extra or [], dry_run=dry_run)
    raise typer.Exit(code=exit_code)
