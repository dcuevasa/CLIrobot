"""Core Dataset Tools Adapter: Exposes prune, split, and annotations as a DatasetTransformPlugin."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
import typer
from rich.prompt import Confirm, Prompt

from clirobot.plugins.base import (
    BasePlugin,
    DatasetTransformPlugin,
    DatasetTransformResult,
    DatasetTransformSpec,
    PluginContext,
    PluginMetadata,
    TUIMenuContribution,
)
from clirobot.ui.console import print_error, print_success


class CoreDatasetPlugin(DatasetTransformPlugin):
    """Adapts built-in prune, split, and annotations engines to the common plugin standard."""

    metadata = PluginMetadata(
        id="core-dataset",
        name="Core Dataset Tools",
        version="0.1.0",
        description="Dataset pruning (depth/6DoF), temporal annotation splitting, and language inspection.",
        category="dataset",
        author="CLIrobot Contributors",
    )

    def get_transforms(self) -> list[DatasetTransformSpec]:
        return [
            DatasetTransformSpec(
                id="prune",
                name="Prune Dataset (Depth / Extra DoFs)",
                description="Drop heavy depth streams and slice robot states/actions to 6 DoF for ACT/Diffusion.",
                icon="🧹",
                supports_in_place=True,
                supports_dry_run=True,
                supports_hub_push=True,
            ),
            DatasetTransformSpec(
                id="split",
                name="Split Dataset by Annotations",
                description="Split episodes into focused subdatasets based on visualizer task/subtask annotations.",
                icon="🔪",
                supports_in_place=False,
                supports_dry_run=True,
                supports_hub_push=True,
            ),
            DatasetTransformSpec(
                id="inspect-annotations",
                name="Inspect Dataset Annotations",
                description="Summarize language instructions, subtasks, VQA tags, and frame counts in dataset.",
                icon="🔍",
                supports_in_place=True,
                supports_dry_run=True,
                supports_hub_push=False,
            ),
        ]

    def execute_transform(
        self,
        transform_id: str,
        ctx: PluginContext,
        input_repo: str,
        output_dir: Optional[str] = None,
        output_repo: Optional[str] = None,
        push_to_hub: bool = False,
        dry_run: bool = False,
        **kwargs: Any,
    ) -> DatasetTransformResult:
        if transform_id == "prune":
            from clirobot.dataset.prune import prune_dataset

            drop_depth = kwargs.get("drop_depth", True)
            drop_ee = kwargs.get("drop_ee", True)
            slice_dof = kwargs.get("slice_dof", None)
            res = prune_dataset(
                dataset_path=input_repo,
                output_path=output_dir,
                drop_depth=drop_depth,
                drop_ee=drop_ee,
                slice_dof=slice_dof,
                push_to_hub=push_to_hub,
                output_repo_id=output_repo,
                dry_run=dry_run,
            )
            return DatasetTransformResult(
                transform_id="prune",
                success=True,
                input_repo_or_path=input_repo,
                output_path=str(res.output_path),
                output_repo_id=output_repo,
                metrics={
                    "modified_parquets": res.modified_parquets,
                    "dropped_columns": res.dropped_columns,
                    "deleted_video_folders": res.deleted_video_folders,
                },
            )

        elif transform_id == "split":
            from clirobot.dataset.split import split_dataset

            annotation_type = kwargs.get("annotation_type", "subtask")
            target_subtasks = kwargs.get("subtasks", None)
            results = split_dataset(
                dataset_path=input_repo,
                output_dir=output_dir or "./subdatasets",
                annotation_type=annotation_type,
                target_subtasks=target_subtasks,
                push_to_hub=push_to_hub,
                hub_repo_id=output_repo,
                dry_run=dry_run,
            )
            total_frames = sum(r.total_frames for r in results)
            return DatasetTransformResult(
                transform_id="split",
                success=True,
                input_repo_or_path=input_repo,
                output_path=output_dir or "./subdatasets",
                output_repo_id=output_repo,
                episodes_processed=sum(r.num_episodes for r in results),
                frames_processed=total_frames,
                metrics={"splits_count": len(results)},
            )

        elif transform_id == "inspect-annotations":
            from clirobot.dataset.annotations import inspect_annotations

            summary = inspect_annotations(Path(input_repo))
            return DatasetTransformResult(
                transform_id="inspect-annotations",
                success=True,
                input_repo_or_path=input_repo,
                episodes_processed=summary.total_episodes,
                metrics={
                    "annotated_episodes": summary.annotated_episodes,
                    "styles": list(summary.by_style.keys()),
                },
            )

        raise ValueError(f"Unknown transform_id: {transform_id}")

    def run_interactive_wizard(self, transform_id: str, ctx: PluginContext) -> None:
        profile = ctx.active_profile
        repo = Prompt.ask("Dataset path or HF repo ID", default=profile.dataset_repo_id)

        if transform_id == "prune":
            from clirobot.dataset.prune import display_prune_result

            drop_d = Confirm.ask("Drop depth observation streams & videos?", default=True)
            drop_e = Confirm.ask("Slice state and action to 6 DoF (remove extra EE axes)?", default=True)
            out_p = Prompt.ask("Destination directory (leave blank for in-place / temp)", default="")
            try:
                res = self.execute_transform(
                    "prune",
                    ctx,
                    input_repo=repo,
                    output_dir=out_p if out_p.strip() else None,
                    drop_depth=drop_d,
                    drop_ee=drop_e,
                )
                from clirobot.dataset.prune import PruneResult

                p_res = PruneResult(
                    input_path=res.input_repo_or_path,
                    output_path=res.output_path or "",
                    modified_parquets=res.metrics.get("modified_parquets", 0),
                    dropped_columns=res.metrics.get("dropped_columns", []),
                    deleted_video_folders=res.metrics.get("deleted_video_folders", []),
                )
                display_prune_result(p_res)
            except Exception as e:
                print_error(f"Prune error: {e}")

        elif transform_id == "split":
            from clirobot.dataset.split import display_split_results

            strategy = Prompt.ask(
                "Annotation split strategy",
                choices=["subtask", "task_aug", "plan", "vqa", "speech"],
                default="subtask",
            )
            out_d = Prompt.ask("Output directory for subdatasets", default="./subdatasets")
            drop_d = Confirm.ask("Drop depth streams during split?", default=False)
            drop_e = Confirm.ask("Slice state/actions to 6 DoF during split?", default=False)
            try:
                from clirobot.dataset.split import split_dataset

                results = split_dataset(
                    dataset_path=repo,
                    output_dir=out_d,
                    annotation_type=strategy,
                    drop_depth=drop_d,
                    drop_ee=drop_e,
                    overwrite=True,
                )
                display_split_results(results)
            except Exception as e:
                print_error(f"Split error: {e}")

        elif transform_id == "inspect-annotations":
            from clirobot.dataset.annotations import display_annotation_summary, inspect_annotations

            try:
                summary = inspect_annotations(Path(repo))
                display_annotation_summary(summary)
            except Exception as e:
                print_error(f"Annotation error: {e}")
