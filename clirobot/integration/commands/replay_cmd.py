"""CLI subcommand for replaying recorded episodes on follower robot arm."""

import typer
from typing import Optional, List
from clirobot.config.manager import ConfigManager
from clirobot.integration.args_builder import LeRobotArgsBuilder
from clirobot.integration.runner import CommandRunner
from clirobot.ui.console import console

app = typer.Typer(help="Replay recorded dataset episodes on the follower arm.", no_args_is_help=False)


@app.callback(invoke_without_command=True)
def replay_episode(
    ctx: typer.Context,
    episode: int = typer.Option(0, "--episode", "-e", help="Episode index to replay"),
    repo_id: Optional[str] = typer.Option(None, "--repo-id", "-r", help="Hugging Face dataset repository ID"),
    fps: Optional[int] = typer.Option(None, "--fps", help="Replay FPS"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Replay an episode from a dataset onto the physical robot."""
    mgr = ConfigManager()
    profile = mgr.get_active_profile()

    args = LeRobotArgsBuilder.build_replay_args(
        profile,
        repo_id=repo_id,
        episode=episode,
        fps=fps,
        extra_args=extra,
    )

    runner = CommandRunner(mgr)
    exit_code = runner.run("replay", args, dry_run=dry_run)
    raise typer.Exit(code=exit_code)
