"""CLI subcommands for info, annotate, tokenizer training, and checkpoint conversion."""

import typer
from typing import Optional, List
from clirobot.config.manager import ConfigManager
from clirobot.integration.runner import CommandRunner

info_app = typer.Typer(help="Inspect robot hardware environment and dataset metadata.", no_args_is_help=False)
annotate_app = typer.Typer(help="Annotate dataset episodes with language descriptions.", no_args_is_help=False)
tokenizer_app = typer.Typer(help="Train action or visual tokenizers.", no_args_is_help=False)
convert_app = typer.Typer(help="Convert distributed checkpoints (DCP).", no_args_is_help=False)


@info_app.callback(invoke_without_command=True)
def print_info_command(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Run lerobot-info to display hardware and platform environment details."""
    mgr = ConfigManager()
    runner = CommandRunner(mgr)
    exit_code = runner.run("info", extra or [], dry_run=dry_run)
    raise typer.Exit(code=exit_code)


@annotate_app.callback(invoke_without_command=True)
def annotate_episodes(
    ctx: typer.Context,
    repo_id: Optional[str] = typer.Option(None, "--repo-id", "-r", help="Dataset repo ID"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Run lerobot-annotate for interactive dataset episode annotation."""
    mgr = ConfigManager()
    profile = mgr.get_active_profile()
    args = []
    target_repo = repo_id or profile.dataset_repo_id
    if target_repo:
        args.append(f"--repo-id={target_repo}")
    if extra:
        args.extend(extra)
    runner = CommandRunner(mgr)
    exit_code = runner.run("annotate", args, dry_run=dry_run)
    raise typer.Exit(code=exit_code)


@tokenizer_app.callback(invoke_without_command=True)
def train_tokenizer(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Run lerobot-train-tokenizer."""
    mgr = ConfigManager()
    runner = CommandRunner(mgr)
    exit_code = runner.run("train-tokenizer", extra or [], dry_run=dry_run)
    raise typer.Exit(code=exit_code)


@convert_app.callback(invoke_without_command=True)
def convert_dcp(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Run lerobot-convert-dcp to convert PyTorch distributed checkpoints."""
    mgr = ConfigManager()
    runner = CommandRunner(mgr)
    exit_code = runner.run("convert-dcp", extra or [], dry_run=dry_run)
    raise typer.Exit(code=exit_code)
