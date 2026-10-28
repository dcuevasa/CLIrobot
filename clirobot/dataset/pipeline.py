"""Composable dataset manipulation pipeline engine for CLIrobot.

Allows chaining multiple dataset transformation steps (e.g., temporal split -> prune -> vision augment -> push to hub)
across core tools and third-party plugins.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional
import typer
from rich.panel import Panel
from rich.table import Table

from clirobot.config.manager import ConfigManager
from clirobot.integration.runner import CommandRunner
from clirobot.plugins.base import DatasetTransformPlugin, DatasetTransformResult, DatasetTransformSpec, PluginContext
from clirobot.plugins.manager import PluginManager
from clirobot.ui.console import console, create_table, print_error, print_info, print_success

logger = logging.getLogger("clirobot.dataset.pipeline")


@dataclass
class PipelineStep:
    """A single transformation step in a dataset pipeline."""

    transform: str
    params: dict[str, Any] = field(default_factory=dict)
    name: Optional[str] = None


@dataclass
class PipelineResult:
    """Cumulative result of a pipeline execution."""

    success: bool
    initial_input: str
    final_output: Optional[str] = None
    final_repo_id: Optional[str] = None
    step_results: list[DatasetTransformResult] = field(default_factory=list)


class DatasetPipelineEngine:
    """Coordinates and executes multi-step dataset manipulation pipelines."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config_manager = config_manager or ConfigManager()
        self.plugin_manager = PluginManager(self.config_manager)
        self.runner = CommandRunner(self.config_manager)
        self.ctx = PluginContext(self.config_manager, self.runner, console)

    def list_available_transforms(self) -> dict[str, tuple[DatasetTransformPlugin, DatasetTransformSpec]]:
        """Discover all transforms registered across all active plugins."""
        return self.plugin_manager.get_dataset_transforms()

    def run_pipeline(
        self,
        steps: list[PipelineStep],
        initial_input: str,
        output_dir: Optional[str] = None,
        final_repo_id: Optional[str] = None,
        push_to_hub: bool = False,
        dry_run: bool = False,
    ) -> PipelineResult:
        """Execute a sequential pipeline of dataset transforms."""
        available = self.list_available_transforms()
        step_results: list[DatasetTransformResult] = []
        current_input = initial_input

        console.print(
            Panel(
                f"[bold cyan]Pipeline Execution Plan:[/bold cyan] {len(steps)} step(s)\n"
                f"  • Initial Dataset: [bold]{initial_input}[/bold]\n"
                f"  • Final Hub Push:  {push_to_hub} ({final_repo_id or 'None'})\n"
                f"  • Dry Run:         {dry_run}",
                title="[bold green]🛠️ CLIrobot Dataset Pipeline[/bold green]",
                border_style="bright_blue",
                padding=(1, 2),
            )
        )

        for idx, step in enumerate(steps, 1):
            if step.transform not in available:
                print_error(f"Step {idx}: Transform '{step.transform}' not found. Available: {list(available.keys())}")
                return PipelineResult(
                    success=False,
                    initial_input=initial_input,
                    step_results=step_results,
                )

            plugin, spec = available[step.transform]
            step_name = step.name or spec.name
            console.print(f"\n[bold yellow]Step {idx}/{len(steps)}:[/bold yellow] {spec.icon} [bold]{step_name}[/bold]")

            is_last_step = (idx == len(steps))
            step_out_dir = output_dir if is_last_step else f"{output_dir or './temp_pipeline'}/step_{idx}"
            step_push = push_to_hub if is_last_step else False
            step_repo = final_repo_id if is_last_step else None

            # Merge step params
            kwargs = dict(step.params)

            try:
                result = plugin.execute_transform(
                    transform_id=step.transform,
                    ctx=self.ctx,
                    input_repo=current_input,
                    output_dir=step_out_dir,
                    output_repo=step_repo,
                    push_to_hub=step_push,
                    dry_run=dry_run,
                    **kwargs,
                )
                step_results.append(result)

                if not result.success:
                    print_error(f"Step {idx} ({step.transform}) failed. Aborting pipeline.")
                    return PipelineResult(
                        success=False,
                        initial_input=initial_input,
                        step_results=step_results,
                    )

                # Set input for next step if output_path was generated
                if result.output_path and not dry_run:
                    current_input = result.output_path

            except Exception as e:
                print_error(f"Exception during step {idx} ({step.transform}): {e}")
                return PipelineResult(
                    success=False,
                    initial_input=initial_input,
                    step_results=step_results,
                )

        console.print("\n[bold green]✔ All pipeline steps executed successfully![/bold green]\n")
        return PipelineResult(
            success=True,
            initial_input=initial_input,
            final_output=current_input,
            final_repo_id=final_repo_id,
            step_results=step_results,
        )


def load_pipeline_recipe(path: Path | str) -> tuple[str, list[PipelineStep], dict[str, Any]]:
    """Load a pipeline recipe from JSON or YAML file."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Recipe file not found: {p}")

    with open(p, "r", encoding="utf-8") as f:
        content = f.read()

    # Try JSON
    try:
        data = json.loads(content)
    except Exception:
        import yaml
        data = yaml.safe_load(content)

    initial_input = data.get("input", "")
    meta = data.get("meta", {})
    raw_steps = data.get("steps", [])

    steps = [
        PipelineStep(
            transform=s["transform"],
            params=s.get("params", {}),
            name=s.get("name"),
        )
        for s in raw_steps
    ]
    return initial_input, steps, meta
