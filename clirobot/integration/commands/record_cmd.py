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
    display_data: bool = typer.Option(False, "--display-data", "--rerun", help="Launch Rerun live data visualizer"),
    play_sounds: bool = typer.Option(False, "--play-sounds", help="Play audible voice / sound cues for episode events"),
    streaming_encoding: bool = typer.Option(False, "--streaming-encoding", help="Stream-encode videos asynchronously for instant saves"),
    reset_every_episode: bool = typer.Option(False, "--reset-every-episode", help="Reset robot or scene between episodes"),
    resume: bool = typer.Option(False, "--resume", help="Resume recording into an existing dataset"),
    batch_encoding_size: Optional[int] = typer.Option(None, "--batch-encoding-size", help="Video encoding batch size"),
    private: bool = typer.Option(False, "--private", help="Create private repository on Hub"),
    tags: Optional[List[str]] = typer.Option(None, "--tag", help="Dataset tags for Hub"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Record episodes with hotkeys for manual flow, discard/retry, buffer clearing, and instant saves."""
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
        display_data=display_data,
        play_sounds=play_sounds,
        streaming_encoding=streaming_encoding,
        reset_every_episode=reset_every_episode,
        resume=resume,
        batch_encoding_size=batch_encoding_size,
        private=private,
        tags=tags,
        extra_args=extra,
    )

    qol_badges = []
    if display_data:
        qol_badges.append("Rerun Viz")
    if streaming_encoding:
        qol_badges.append("Streaming Encode")
    if play_sounds:
        qol_badges.append("Audio Cues")
    if reset_every_episode:
        qol_badges.append("Scene Reset")
    if resume:
        qol_badges.append("Resume")

    console.print(
        build_hud_panel(
            status="RECORDING",
            episode_index=1,
            total_episodes=episodes,
            fps=float(fps or profile.default_fps),
            backend="Enhanced TTY / Safe Mode",
            qol_features=qol_badges if qol_badges else None,
        )
    )

    runner = CommandRunner(mgr)
    exit_code = runner.run("record", args, dry_run=dry_run)
    raise typer.Exit(code=exit_code)
