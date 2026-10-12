"""CLI subcommands for dataset management, visualization, editing, and sidecar building."""

import typer
from typing import Optional, List
from clirobot.config.manager import ConfigManager
from clirobot.integration.runner import CommandRunner

app = typer.Typer(help="Inspect, edit, visualize, and build sidecars for datasets.", no_args_is_help=False)


@app.command("viz")
def visualize_dataset(
    repo_id: Optional[str] = typer.Option(None, "--repo-id", "-r", help="Dataset repo ID"),
    episode: int = typer.Option(0, "--episode", "-e", help="Initial episode index"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Launch Rerun / web dataset visualizer (lerobot-dataset-viz)."""
    mgr = ConfigManager()
    profile = mgr.get_active_profile()

    args = []
    target_repo = repo_id or profile.dataset_repo_id
    if target_repo:
        args.append(f"--repo-id={target_repo}")
    args.append(f"--episode-index={episode}")

    if extra:
        args.extend(extra)

    runner = CommandRunner(mgr)
    exit_code = runner.run("dataset-viz", args, dry_run=dry_run)
    raise typer.Exit(code=exit_code)


@app.command("edit")
def edit_dataset(
    repo_id: Optional[str] = typer.Option(None, "--repo-id", "-r", help="Dataset repo ID"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Edit, filter, or trim dataset episodes (lerobot-edit-dataset)."""
    mgr = ConfigManager()
    profile = mgr.get_active_profile()

    args = []
    target_repo = repo_id or profile.dataset_repo_id
    if target_repo:
        args.append(f"--repo-id={target_repo}")

    if extra:
        args.extend(extra)

    runner = CommandRunner(mgr)
    exit_code = runner.run("edit-dataset", args, dry_run=dry_run)
    raise typer.Exit(code=exit_code)


@app.command("transform-viz")
def transform_viz(
    repo_id: Optional[str] = typer.Option(None, "--repo-id", "-r", help="Dataset repo ID"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Visualize image transformations and augmentations (lerobot-imgtransform-viz)."""
    mgr = ConfigManager()
    profile = mgr.get_active_profile()

    args = []
    target_repo = repo_id or profile.dataset_repo_id
    if target_repo:
        args.append(f"--repo-id={target_repo}")

    if extra:
        args.extend(extra)

    runner = CommandRunner(mgr)
    exit_code = runner.run("imgtransform-viz", args, dry_run=dry_run)
    raise typer.Exit(code=exit_code)


@app.command("sidecar")
def build_sidecar(
    repo_id: Optional[str] = typer.Option(None, "--repo-id", "-r", help="Dataset repo ID"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Build MP4 video sidecars for fast streaming playback (lerobot-build-mp4-sidecar)."""
    mgr = ConfigManager()
    profile = mgr.get_active_profile()

    args = []
    target_repo = repo_id or profile.dataset_repo_id
    if target_repo:
        args.append(f"--repo-id={target_repo}")

    if extra:
        args.extend(extra)

    runner = CommandRunner(mgr)
    exit_code = runner.run("build-mp4-sidecar", args, dry_run=dry_run)
    raise typer.Exit(code=exit_code)
