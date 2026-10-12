"""CLI subcommand for dataset demonstration recording."""

import typer
from typing import Optional, List
from clirobot.config.manager import ConfigManager
from clirobot.integration.args_builder import LeRobotArgsBuilder
from clirobot.integration.runner import CommandRunner
from clirobot.ui.console import console, print_info, print_warning
from clirobot.ui.hud import build_hud_panel

app = typer.Typer(help="Record robot demonstration datasets with keyboard controls.", no_args_is_help=False)


@app.callback(invoke_without_command=True)
def record_demonstrations(
    ctx: typer.Context,
    repo_id: Optional[str] = typer.Option(None, "--repo-id", "-r", help="Hugging Face dataset repository ID"),
    episodes: int = typer.Option(10, "--episodes", "-n", help="Number of episodes to record"),
    episode_time: float = typer.Option(30.0, "--episode-time", help="Max seconds per episode"),
    warmup_time: float = typer.Option(3.0, "--warmup-time", help="Warmup seconds before recording starts"),
    reset_time: float = typer.Option(5.0, "--reset-time", help="Reset seconds between episodes"),
    task: Optional[str] = typer.Option(None, "--task", "-t", help="Natural language description of the task"),
    fps: Optional[int] = typer.Option(None, "--fps", help="Recording FPS"),
    push_to_hub: bool = typer.Option(False, "--push-to-hub", help="Upload dataset to Hugging Face Hub after recording"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Record episodes with hotkeys for pause, re-record, and episode saving."""
    mgr = ConfigManager()
    profile = mgr.get_active_profile()

    args = LeRobotArgsBuilder.build_record_args(
        profile,
        repo_id=repo_id,
        num_episodes=episodes,
        episode_time_s=episode_time,
        warmup_time_s=warmup_time,
        reset_time_s=reset_time,
        single_task=task,
        fps=fps,
        push_to_hub=push_to_hub,
        extra_args=extra,
    )

    console.print(
        build_hud_panel(
            status="RECORDING",
            episode_index=1,
            total_episodes=episodes,
            fps=float(fps or profile.default_fps),
            backend="Enhanced TTY / Safe Mode",
        )
    )

    runner = CommandRunner(mgr)
    exit_code = runner.run("record", args, dry_run=dry_run)
    raise typer.Exit(code=exit_code)
