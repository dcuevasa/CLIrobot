"""CLI subcommand for robot teleoperation."""

import typer
from typing import Optional, List
from clirobot.config.manager import ConfigManager
from clirobot.integration.args_builder import LeRobotArgsBuilder
from clirobot.integration.runner import CommandRunner
from clirobot.ui.console import console, print_info, print_warning
from clirobot.ui.hud import build_hud_panel

app = typer.Typer(help="Live teleoperation for robot arms.", no_args_is_help=False)


@app.callback(invoke_without_command=True)
def teleoperate(
    ctx: typer.Context,
    fps: Optional[int] = typer.Option(None, "--fps", help="Target loop FPS"),
    display_cameras: bool = typer.Option(True, "--display-cameras/--no-cameras", help="Show live camera preview"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Start teleoperation between Leader and Follower arms using profile settings."""
    mgr = ConfigManager()
    profile = mgr.get_active_profile()

    if not profile.leader_arm.port and not any(a.startswith("--teleop.port") for a in (extra or [])):
        print_warning(
            f"No Leader port is configured in active profile '{profile.name}'.\n"
            "Run [bold cyan]clirobot ports find[/bold cyan] to detect and assign your leader arm, or pass --teleop.port=..."
        )

    if not profile.follower_arm.port and not any(a.startswith("--robot.port") for a in (extra or [])):
        print_warning(
            f"No Follower port is configured in active profile '{profile.name}'.\n"
            "Run [bold cyan]clirobot ports find[/bold cyan] to detect and assign your follower arm, or pass --robot.port=..."
        )

    args = LeRobotArgsBuilder.build_teleoperate_args(
        profile,
        fps=fps,
        display_cameras=display_cameras,
        extra_args=extra,
    )

    console.print(
        build_hud_panel(
            status="TELEOPERATING",
            fps=float(fps or profile.default_fps),
            backend="Terminal Raw / GUI",
        )
    )

    runner = CommandRunner(mgr)
    exit_code = runner.run("teleoperate", args, dry_run=dry_run)
    raise typer.Exit(code=exit_code)
