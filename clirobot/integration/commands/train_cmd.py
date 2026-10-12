"""CLI subcommand for training imitation learning policies."""

import typer
from typing import Optional, List
from clirobot.config.manager import ConfigManager
from clirobot.constants import SUPPORTED_POLICIES
from clirobot.integration.args_builder import LeRobotArgsBuilder
from clirobot.integration.runner import CommandRunner
from clirobot.ui.console import console, print_info
from clirobot.ui.prompts import prompt_select, prompt_text, prompt_confirm

app = typer.Typer(help="Train imitation learning policies (ACT, Diffusion, SmolVLM, etc.).", no_args_is_help=False)


@app.callback(invoke_without_command=True)
def train_policy(
    ctx: typer.Context,
    dataset: Optional[str] = typer.Option(None, "--dataset", "-d", help="Dataset repo ID (e.g. lerobot/aloha_sim_insertion_human)"),
    policy: str = typer.Option("act", "--policy", "-p", help="Policy architecture (act, diffusion, tdmpc, smolvlm)"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", "-o", help="Checkpoint output directory"),
    batch_size: int = typer.Option(8, "--batch-size", "-b", help="Training batch size"),
    steps: int = typer.Option(100000, "--steps", "-s", help="Total training steps"),
    device: str = typer.Option("cuda", "--device", help="Computation device (cuda, mps, cpu)"),
    wandb: bool = typer.Option(False, "--wandb", help="Enable Weights & Biases logging"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Launch interactive training setup wizard"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Launch imitation learning policy training."""
    mgr = ConfigManager()
    profile = mgr.get_active_profile()

    target_dataset = dataset or profile.dataset_repo_id

    if interactive:
        console.print("\n[bold cyan]⚡ Interactive Policy Training Wizard[/bold cyan]\n")
        target_dataset = prompt_text("Dataset repo ID:", default=target_dataset)
        policy = prompt_select("Select Policy Architecture:", SUPPORTED_POLICIES, default=policy)
        batch_size = int(prompt_text("Batch size:", default=str(batch_size)))
        steps = int(prompt_text("Total training steps:", default=str(steps)))
        wandb = prompt_confirm("Enable Weights & Biases tracking?", default=wandb)

    args = LeRobotArgsBuilder.build_train_args(
        dataset_repo_id=target_dataset,
        policy_type=policy,
        output_dir=output_dir,
        batch_size=batch_size,
        steps=steps,
        device=device,
        wandb_enable=wandb,
        extra_args=extra,
    )

    runner = CommandRunner(mgr)
    exit_code = runner.run("train", args, dry_run=dry_run)
    raise typer.Exit(code=exit_code)
