"""LeRobot dataset pruning and trimming engine.

Strips heavy or unnecessary streams (depth cameras, extra end-effector degrees of freedom,
or arbitrary observation/action features) from parquet tables, video streams, and metadata
for efficient model training (ACT, Diffusion Policy, SmolVLA).
"""

from __future__ import annotations

import glob
import json
import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

import pandas as pd
from rich.panel import Panel
from rich.table import Table

from clirobot.ui.console import console

logger = logging.getLogger("clirobot.dataset.prune")

DEFAULT_6DOF_NAMES = [
    "shoulder_pan.pos",
    "shoulder_lift.pos",
    "elbow_flex.pos",
    "wrist_flex.pos",
    "wrist_roll.pos",
    "gripper.pos",
]


@dataclass
class PruneResult:
    """Statistical summary of dataset pruning results."""

    input_path: str
    output_path: str
    modified_parquets: int = 0
    dropped_columns: list[str] = field(default_factory=list)
    deleted_video_folders: list[str] = field(default_factory=list)
    updated_features: list[str] = field(default_factory=list)
    sliced_dof: Optional[int] = None
    hub_url: Optional[str] = None


def prune_dataset(
    dataset_path: str | Path,
    output_path: Optional[str | Path] = None,
    drop_depth: bool = False,
    drop_ee: bool = False,
    slice_dof: Optional[int] = None,
    slice_names: Optional[List[str]] = None,
    drop_features: Optional[List[str]] = None,
    clean_meta: bool = True,
    push_to_hub: bool = False,
    output_repo_id: Optional[str] = None,
    hf_token: Optional[str] = None,
    private: bool = False,
    commit_message: Optional[str] = None,
    dry_run: bool = False,
) -> PruneResult:
    """Prune features, video streams, and metadata from a LeRobot dataset.

    Args:
        dataset_path: Local directory path or Hugging Face repository ID.
        output_path: Destination local directory (if None, prunes in-place for local).
        drop_depth: Drop all depth camera observations and video directories.
        drop_ee: Slice state and action vectors to 6 DoF.
        slice_dof: Custom number of degrees of freedom to slice state/action.
        slice_names: Custom joint names for the sliced degrees of freedom.
        drop_features: Specific feature column names to drop.
        clean_meta: Standardize loose metadata files into meta/ directory.
        push_to_hub: Upload the pruned dataset to Hugging Face Hub.
        output_repo_id: Hugging Face repo ID for hub upload.
        hf_token: Hugging Face API token.
        private: Create private repository on Hub if pushing.
        commit_message: Commit message for Hub upload.
        dry_run: Inspect without writing changes.

    Returns:
        PruneResult summary object.
    """
    input_str = str(dataset_path).strip()
    target_dof = slice_dof or (6 if drop_ee else None)
    names_to_use = slice_names or (DEFAULT_6DOF_NAMES[:target_dof] if target_dof and target_dof <= 6 else None)

    # 1. Resolve source dataset (download if remote HF repo)
    is_remote = not Path(input_str).exists() and ("/" in input_str)
    temp_download_dir: Optional[Path] = None

    if is_remote:
        from huggingface_hub import snapshot_download

        temp_download_dir = Path("./temp_dataset_download")
        if temp_download_dir.exists():
            shutil.rmtree(temp_download_dir)
        temp_download_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Downloading dataset from Hugging Face Hub: {input_str}...")
        snapshot_download(repo_id=input_str, repo_type="dataset", local_dir=str(temp_download_dir))
        work_src = temp_download_dir
    else:
        work_src = Path(input_str).resolve()
        if not work_src.exists():
            raise FileNotFoundError(f"Source dataset directory does not exist: {input_str}")

    # 2. Determine target working directory
    if output_path is not None:
        work_dst = Path(output_path).resolve()
        if work_dst != work_src:
            if not dry_run:
                if work_dst.exists():
                    shutil.rmtree(work_dst)
                work_dst.parent.mkdir(parents=True, exist_ok=True)
                logger.info(f"Copying {work_src} to {work_dst}...")
                shutil.copytree(work_src, work_dst)
    else:
        work_dst = work_src

    result = PruneResult(
        input_path=str(dataset_path),
        output_path=str(work_dst),
        sliced_dof=target_dof,
    )

    dropped_cols_set: set[str] = set()
    features_to_drop_list = [f.strip() for f in (drop_features or []) if f.strip()]

    # 3. Prune Parquet Tables
    parquet_files = sorted(glob.glob(os.path.join(str(work_dst), "data", "**", "*.parquet"), recursive=True))
    if not parquet_files:
        # Check root or chunk directories
        parquet_files = sorted(glob.glob(os.path.join(str(work_dst), "**", "*.parquet"), recursive=True))
        # Exclude meta parquet
        parquet_files = [p for p in parquet_files if "meta" not in Path(p).parts]

    for p_file in parquet_files:
        df = pd.read_parquet(p_file)
        modified = False

        # Drop depth columns
        if drop_depth:
            depth_cols = [col for col in df.columns if "depth" in col.lower()]
            if depth_cols:
                df = df.drop(columns=depth_cols, errors="ignore")
                dropped_cols_set.update(depth_cols)
                modified = True

        # Drop specific features
        if features_to_drop_list:
            explicit_cols = [c for c in features_to_drop_list if c in df.columns]
            if explicit_cols:
                df = df.drop(columns=explicit_cols, errors="ignore")
                dropped_cols_set.update(explicit_cols)
                modified = True

        # Slice state / action vectors
        if target_dof is not None:
            for col in ["observation.state", "action"]:
                if col in df.columns:
                    df[col] = df[col].apply(
                        lambda x: list(x)[:target_dof] if hasattr(x, "__len__") and len(x) >= target_dof else x
                    )
                    modified = True

        if modified:
            result.modified_parquets += 1
            if not dry_run:
                df.to_parquet(p_file, index=False)

    result.dropped_columns = sorted(dropped_cols_set)

    # 4. Delete Matching Video Directories
    videos_dir = work_dst / "videos"
    if videos_dir.exists():
        for vid_folder in list(videos_dir.rglob("*")):
            if vid_folder.is_dir():
                folder_name = vid_folder.name.lower()
                should_delete = False
                if drop_depth and "depth" in folder_name:
                    should_delete = True
                for ftd in features_to_drop_list:
                    if ftd.lower() in folder_name:
                        should_delete = True

                if should_delete:
                    result.deleted_video_folders.append(vid_folder.name)
                    if not dry_run:
                        shutil.rmtree(vid_folder, ignore_errors=True)

    # 5. Enforce meta/ Directory Structure
    meta_dir = work_dst / "meta"
    if clean_meta and not dry_run:
        meta_dir.mkdir(parents=True, exist_ok=True)
        for meta_filename in [
            "info.json",
            "stats.json",
            "episodes.jsonl",
            "episodes.json",
            "tasks.parquet",
            "episodes.parquet",
            "lerobot_annotations.json",
        ]:
            root_candidate = work_dst / meta_filename
            meta_target = meta_dir / meta_filename
            if root_candidate.exists() and root_candidate != meta_target:
                shutil.move(str(root_candidate), str(meta_target))

    # 6. Update meta/info.json
    info_path = meta_dir / "info.json"
    if info_path.exists():
        with open(info_path, "r", encoding="utf-8") as f:
            info = json.load(f)

        features = info.get("features", {})
        info_modified = False

        if drop_depth:
            depth_keys = [k for k in features.keys() if "depth" in k.lower()]
            for k in depth_keys:
                features.pop(k, None)
                result.updated_features.append(f"removed:{k}")
                info_modified = True

        if features_to_drop_list:
            for k in features_to_drop_list:
                if k in features:
                    features.pop(k, None)
                    result.updated_features.append(f"removed:{k}")
                    info_modified = True

        if target_dof is not None:
            for col in ["observation.state", "action"]:
                if col in features:
                    features[col]["shape"] = [target_dof]
                    if names_to_use:
                        features[col]["names"] = names_to_use
                    elif "names" in features[col] and isinstance(features[col]["names"], list):
                        features[col]["names"] = features[col]["names"][:target_dof]
                    result.updated_features.append(f"sliced:{col}->{target_dof}DoF")
                    info_modified = True

        if info_modified and not dry_run:
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(info, f, indent=4)

    # 7. Update meta/stats.json
    stats_path = meta_dir / "stats.json"
    if stats_path.exists():
        with open(stats_path, "r", encoding="utf-8") as f:
            stats = json.load(f)

        stats_modified = False

        if drop_depth:
            depth_stat_keys = [k for k in stats.keys() if "depth" in k.lower()]
            for k in depth_stat_keys:
                stats.pop(k, None)
                stats_modified = True

        if features_to_drop_list:
            for k in features_to_drop_list:
                if k in stats:
                    stats.pop(k, None)
                    stats_modified = True

        if target_dof is not None:
            for col in ["observation.state", "action"]:
                if col in stats and isinstance(stats[col], dict):
                    for metric, val in stats[col].items():
                        if isinstance(val, list):
                            stats[col][metric] = val[:target_dof]
                    stats_modified = True

        if stats_modified and not dry_run:
            with open(stats_path, "w", encoding="utf-8") as f:
                json.dump(stats, f, indent=4)

    # 8. Upload to Hugging Face Hub if requested
    if push_to_hub and output_repo_id and not dry_run:
        from huggingface_hub import HfApi

        token = hf_token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        api = HfApi(token=token)
        logger.info(f"Creating repository on Hugging Face: {output_repo_id}...")
        api.create_repo(repo_id=output_repo_id, repo_type="dataset", private=private, exist_ok=True)

        msg = commit_message or (
            f"Pruned dataset: dropped depth={drop_depth}, "
            f"sliced_dof={target_dof}, dropped_features={features_to_drop_list}"
        )
        logger.info(f"Uploading pruned dataset to https://huggingface.co/datasets/{output_repo_id}...")
        api.upload_folder(
            folder_path=str(work_dst),
            repo_id=output_repo_id,
            repo_type="dataset",
            commit_message=msg,
        )
        result.hub_url = f"https://huggingface.co/datasets/{output_repo_id}"
        logger.info(f"Upload complete: {result.hub_url}")

    # Clean temporary download dir if used
    if temp_download_dir and temp_download_dir.exists() and output_path is not None:
        shutil.rmtree(temp_download_dir, ignore_errors=True)

    return result


def display_prune_result(result: PruneResult) -> None:
    """Render a Rich formatted summary panel of pruning results."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan", width=22)
    table.add_column(style="white")

    table.add_row("Source Dataset:", result.input_path)
    table.add_row("Pruned Output:", result.output_path)
    table.add_row("Parquet Files Modified:", f"[bold green]{result.modified_parquets}[/bold green]")

    if result.sliced_dof is not None:
        table.add_row("State/Action Sliced To:", f"[bold magenta]{result.sliced_dof} DoF[/bold magenta]")

    if result.dropped_columns:
        table.add_row("Dropped Columns:", f"[yellow]{', '.join(result.dropped_columns)}[/yellow]")

    if result.deleted_video_folders:
        table.add_row("Deleted Video Streams:", f"[red]{', '.join(result.deleted_video_folders)}[/red]")

    if result.updated_features:
        table.add_row("Metadata Updates:", f"[cyan]{', '.join(result.updated_features)}[/cyan]")

    if result.hub_url:
        table.add_row("Hugging Face Hub URL:", f"[bold green underline]{result.hub_url}[/bold green underline]")

    console.print(
        Panel(
            table,
            title="[bold bright_blue]⚡ Dataset Pruning Summary ⚡[/bold bright_blue]",
            border_style="bright_blue",
            padding=(1, 2),
        )
    )
