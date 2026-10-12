"""CLI subcommands for policy evaluation and rollouts."""

import typer
from typing import Optional, List
from clirobot.config.manager import ConfigManager
from clirobot.integration.runner import CommandRunner

eval_app = typer.Typer(help="Evaluate trained policies on physical robots or simulators.", no_args_is_help=False)
rollout_app = typer.Typer(help="Execute policy rollouts.", no_args_is_help=False)


@eval_app.callback(invoke_without_command=True)
def evaluate_policy(
    ctx: typer.Context,
    policy_path: Optional[str] = typer.Option(None, "--policy-path", "-p", help="Path or Hugging Face Hub ID to trained policy checkpoint"),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Evaluation environment"),
    episodes: int = typer.Option(10, "--episodes", "-n", help="Number of evaluation episodes"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Run lerobot-eval to benchmark policy performance."""
    mgr = ConfigManager()
    args: list[str] = []

    if policy_path:
        args.append(f"--policy.path={policy_path}")
    if env:
        args.append(f"--env.type={env}")
    args.append(f"--eval.num_episodes={episodes}")

    if extra:
        args.extend(extra)

    runner = CommandRunner(mgr)
    exit_code = runner.run("eval", args, dry_run=dry_run)
    raise typer.Exit(code=exit_code)


@rollout_app.callback(invoke_without_command=True)
def rollout_policy(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Run lerobot-rollout."""
    mgr = ConfigManager()
    runner = CommandRunner(mgr)
    exit_code = runner.run("rollout", extra or [], dry_run=dry_run)
    raise typer.Exit(code=exit_code)
