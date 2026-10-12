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


@app.command("prune")
def prune_cmd(
    repo_id: Optional[str] = typer.Option(None, "--repo-id", "-r", help="Source dataset repo ID or local path"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Target output directory (defaults to in-place for local)"),
    drop_depth: bool = typer.Option(False, "--drop-depth", help="Drop all depth observation columns and video directories"),
    drop_ee: bool = typer.Option(False, "--drop-ee", help="Slice state and action vectors to 6 DoF (remove extra EE axes)"),
    slice_dof: Optional[int] = typer.Option(None, "--slice-dof", help="Slice state and action vectors to specific DoF count"),
    drop_features: Optional[List[str]] = typer.Option(None, "--drop-feature", help="Specific feature name(s) to drop"),
    push_to_hub: bool = typer.Option(False, "--push-to-hub", help="Upload pruned dataset to Hugging Face Hub"),
    output_repo_id: Optional[str] = typer.Option(None, "--output-repo-id", help="Destination Hugging Face Hub repository ID"),
    private: bool = typer.Option(False, "--private", help="Create private repository on Hugging Face Hub"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect operations without modifying files"),
):
    """Prune heavy or unused streams (depth, extra EE DoFs) to prepare datasets for training."""
    from clirobot.dataset.prune import prune_dataset, display_prune_result

    mgr = ConfigManager()
    profile = mgr.get_active_profile()
    target_source = repo_id or profile.dataset_repo_id

    if not target_source:
        from clirobot.ui.console import print_error
        print_error("No dataset specified. Provide --repo-id or configure dataset_repo_id in profile.")
        raise typer.Exit(code=1)

    result = prune_dataset(
        dataset_path=target_source,
        output_path=output,
        drop_depth=drop_depth,
        drop_ee=drop_ee,
        slice_dof=slice_dof,
        drop_features=drop_features,
        push_to_hub=push_to_hub,
        output_repo_id=output_repo_id,
        private=private,
        dry_run=dry_run,
    )
    display_prune_result(result)


@app.command("split")
def split_cmd(
    repo_id: Optional[str] = typer.Option(None, "--repo-id", "-r", help="Source dataset repo ID or local directory"),
    output_dir: str = typer.Option("./subdatasets", "--output-dir", "-o", help="Destination directory for generated subdatasets"),
    annotation_type: str = typer.Option("subtask", "--annotation-type", "-a", help="Split strategy: subtask, task_aug, plan, vqa, speech"),
    subtasks: Optional[List[str]] = typer.Option(None, "--subtask", "--target-subtask", help="Target subtask filter substring(s)"),
    annotations_file: Optional[str] = typer.Option(None, "--annotations-file", help="Explicit path to lerobot_annotations.json"),
    min_frames: int = typer.Option(5, "--min-frames", help="Minimum frames required for valid split"),
    min_duration: float = typer.Option(0.1, "--min-duration", help="Minimum duration in seconds for valid split"),
    drop_depth: bool = typer.Option(False, "--drop-depth", help="Drop depth streams while splitting"),
    drop_ee: bool = typer.Option(False, "--drop-ee", help="Slice state and action to 6 DoF while splitting"),
    vcodec: str = typer.Option("libsvtav1", "--vcodec", help="Video codec for re-encoded video streams"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing output directory"),
    push_to_hub: bool = typer.Option(False, "--push-to-hub", help="Upload each subdataset to Hugging Face Hub"),
    hub_prefix: Optional[str] = typer.Option(None, "--hub-repo-prefix", help="Hub repository prefix (e.g. org/dataset-subtask-)"),
    hub_repo_id: Optional[str] = typer.Option(None, "--hub-repo-id", help="Single Hub repository ID (when splitting single subtask)"),
    private: bool = typer.Option(False, "--private", help="Create private repository on Hub"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview splits without writing files"),
):
    """Split a dataset into focused subdatasets based on visualizer annotations."""
    from clirobot.dataset.split import split_dataset, display_split_results

    mgr = ConfigManager()
    profile = mgr.get_active_profile()
    target_source = repo_id or profile.dataset_repo_id

    if not target_source:
        from clirobot.ui.console import print_error
        print_error("No dataset specified. Provide --repo-id or configure dataset_repo_id in profile.")
        raise typer.Exit(code=1)

    results = split_dataset(
        dataset_path=target_source,
        output_dir=output_dir,
        annotation_type=annotation_type,
        target_subtasks=subtasks,
        annotations_file=annotations_file,
        min_frames=min_frames,
        min_duration_s=min_duration,
        drop_depth=drop_depth,
        drop_ee=drop_ee,
        vcodec=vcodec,
        overwrite=overwrite,
        push_to_hub=push_to_hub,
        hub_repo_prefix=hub_prefix,
        hub_repo_id=hub_repo_id,
        private=private,
        dry_run=dry_run,
    )
    display_split_results(results, dry_run=dry_run)


@app.command("annotations")
@app.command("list-annotations")
def inspect_annotations_cmd(
    repo_id: Optional[str] = typer.Option(None, "--repo-id", "-r", help="Dataset repo ID or local path"),
    annotations_file: Optional[str] = typer.Option(None, "--annotations-file", help="Explicit path to lerobot_annotations.json"),
):
    """Inspect and summarize annotations (subtasks, VQA, speech) present in a dataset."""
    from pathlib import Path
    from clirobot.dataset.annotations import inspect_annotations, display_annotation_summary

    mgr = ConfigManager()
    profile = mgr.get_active_profile()
    target_source = repo_id or profile.dataset_repo_id

    if not target_source:
        from clirobot.ui.console import print_error
        print_error("No dataset specified. Provide --repo-id or configure dataset_repo_id in profile.")
        raise typer.Exit(code=1)

    summary = inspect_annotations(
        dataset_root=Path(target_source),
        custom_annotations_path=Path(annotations_file) if annotations_file else None,
    )
    display_annotation_summary(summary)
