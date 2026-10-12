"""Dataset splitting engine based on annotations.

Splits LeRobot datasets into subdatasets according to visualizer annotations
(meta/lerobot_annotations.json or embedded parquet language columns) using an extensible
strategy pattern (subtask, task_aug, plan, vqa, speech).
"""

from __future__ import annotations

import argparse
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import glob
import json
import logging
import os
from pathlib import Path
import re
import shutil
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
from rich.panel import Panel
from rich.table import Table

from clirobot.dataset.annotations import (
    load_dataset_annotations,
    sanitize_name,
    sanitize_dataset_metadata,
)
from clirobot.ui.console import console

logger = logging.getLogger("clirobot.dataset.split")

# Default metadata columns not considered robot features
DEFAULT_IGNORE_FEATURES = {
    "timestamp",
    "frame_index",
    "episode_index",
    "index",
    "task_index",
    "task",
    "subtask_index",
    "subtask",
    "next.reward",
    "next.done",
    "next.truncated",
}


@dataclass
class EpisodeSegment:
    """Represents a sliced temporal span of an episode belonging to a subdataset."""

    source_episode_index: int
    start_frame: int
    end_frame: int
    start_timestamp: float
    end_timestamp: float
    label: str
    split_name: str
    annotation_type: str = "subtask"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def num_frames(self) -> int:
        return max(0, self.end_frame - self.start_frame)

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_timestamp - self.start_timestamp)


@dataclass
class SplitResult:
    """Metadata for an extracted subdataset split."""

    split_name: str
    label: str
    annotation_type: str
    segments: list[EpisodeSegment]
    local_output_path: Optional[Path] = None
    hub_repo_id: Optional[str] = None

    @property
    def num_episodes(self) -> int:
        return len(self.segments)

    @property
    def total_frames(self) -> int:
        return sum(s.num_frames for s in self.segments)


# ==============================================================================
# Annotation Splitter Strategies (Extensible Architecture)
# ==============================================================================


class BaseAnnotationSplitter(ABC):
    """Abstract Base Class for splitting a LeRobot dataset based on annotations."""

    @property
    @abstractmethod
    def annotation_type(self) -> str:
        """String identifier for this annotation type."""
        pass

    @abstractmethod
    def extract_splits(
        self,
        dataset_meta: dict[str, Any],
        annotations: dict[int, list[dict[str, Any]]],
        **kwargs,
    ) -> dict[str, list[EpisodeSegment]]:
        """Extract subdataset segments grouped by target split name.

        Args:
            dataset_meta: Metadata dictionary containing total_episodes, fps, episode lengths.
            annotations: Dictionary mapping episode index to list of atom dicts.
            kwargs: Strategy-specific parameters.

        Returns:
            dict mapping split_name -> list of EpisodeSegment
        """
        pass

    def describe(self) -> str:
        return self.__doc__ or self.__class__.__name__


_SPLITTER_REGISTRY: dict[str, type[BaseAnnotationSplitter]] = {}


def register_splitter(name: str):
    """Decorator to register an annotation splitting strategy."""

    def decorator(cls: type[BaseAnnotationSplitter]):
        _SPLITTER_REGISTRY[name.lower()] = cls
        return cls

    return decorator


def get_splitter(name: str) -> BaseAnnotationSplitter:
    """Retrieve an instantiated splitter by name."""
    name_lower = name.lower()
    if name_lower not in _SPLITTER_REGISTRY:
        available = ", ".join(sorted(_SPLITTER_REGISTRY.keys()))
        raise ValueError(f"Unknown annotation type '{name}'. Available types: {available}")
    return _SPLITTER_REGISTRY[name_lower]()


def list_splitters() -> list[str]:
    """List all registered annotation splitter strategy names."""
    return sorted(_SPLITTER_REGISTRY.keys())


# ------------------------------------------------------------------------------
# 1. Subtask Splitter (Primary Focus)
# ------------------------------------------------------------------------------


@register_splitter("subtask")
class SubtaskSplitter(BaseAnnotationSplitter):
    """Splits episodes into subdatasets by subtask spans [t_start, t_end)."""

    @property
    def annotation_type(self) -> str:
        return "subtask"

    def extract_splits(
        self,
        dataset_meta: dict[str, Any],
        annotations: dict[int, list[dict[str, Any]]],
        target_subtasks: Optional[list[str]] = None,
        min_frames: int = 5,
        min_duration_s: float = 0.1,
        snap_first_subtask_to_zero: bool = True,
        **kwargs,
    ) -> dict[str, list[EpisodeSegment]]:
        splits: dict[str, list[EpisodeSegment]] = {}
        fps = float(dataset_meta.get("fps", 30.0))
        total_episodes = int(dataset_meta.get("total_episodes", len(annotations)))
        episode_lengths = dataset_meta.get("episode_lengths", {})

        target_set: Optional[set[str]] = (
            {t.strip().lower() for t in target_subtasks if t.strip()} if target_subtasks else None
        )

        for ep_idx in range(total_episodes):
            ep_length = episode_lengths.get(ep_idx, int(dataset_meta.get("default_length", 300)))
            ep_duration = ep_length / fps

            atoms = annotations.get(ep_idx, [])
            subtask_atoms = [a for a in atoms if a.get("style") == "subtask" and a.get("content")]
            if not subtask_atoms:
                continue

            subtask_atoms.sort(key=lambda a: float(a.get("timestamp", 0.0)))
            num_subtasks = len(subtask_atoms)

            for i, atom in enumerate(subtask_atoms):
                label = str(atom["content"]).strip()
                if not label:
                    continue

                if target_set is not None:
                    label_lower = label.lower()
                    if not any(tgt in label_lower or label_lower in tgt for tgt in target_set):
                        continue

                # Snap first subtask to zero if requested
                if i == 0 and snap_first_subtask_to_zero:
                    start_ts = 0.0
                else:
                    start_ts = float(atom.get("timestamp", 0.0))

                # Handle interval end
                if atom.get("_legacy_end") is not None and float(atom["_legacy_end"]) > start_ts:
                    end_ts = float(atom["_legacy_end"])
                elif i + 1 < num_subtasks:
                    end_ts = float(subtask_atoms[i + 1].get("timestamp", ep_duration))
                else:
                    end_ts = ep_duration

                start_ts = max(0.0, min(start_ts, ep_duration))
                end_ts = max(start_ts, min(end_ts, ep_duration))

                start_frame = int(round(start_ts * fps))
                end_frame = int(round(end_ts * fps))

                start_frame = max(0, min(start_frame, ep_length))
                end_frame = max(start_frame, min(end_frame, ep_length))

                seg_frames = end_frame - start_frame
                seg_duration = end_ts - start_ts

                if seg_frames < min_frames or seg_duration < min_duration_s:
                    continue

                split_slug = sanitize_name(label)

                # Collect other events within window
                segment_events = []
                for other_atom in atoms:
                    if other_atom.get("style") != "subtask":
                        o_ts = float(other_atom.get("timestamp", 0.0))
                        if start_ts <= o_ts < end_ts:
                            shifted = dict(other_atom)
                            shifted["timestamp"] = max(0.0, o_ts - start_ts)
                            segment_events.append(shifted)

                segment = EpisodeSegment(
                    source_episode_index=ep_idx,
                    start_frame=start_frame,
                    end_frame=end_frame,
                    start_timestamp=start_ts,
                    end_timestamp=end_ts,
                    label=label,
                    split_name=split_slug,
                    annotation_type="subtask",
                    metadata={
                        "subtask_index_in_episode": i,
                        "events": segment_events,
                        "original_atom": atom,
                    },
                )
                splits.setdefault(split_slug, []).append(segment)

        return splits


# ------------------------------------------------------------------------------
# 2. Task Augmentation Splitter
# ------------------------------------------------------------------------------


@register_splitter("task_aug")
class TaskAugSplitter(BaseAnnotationSplitter):
    """Splits full episodes based on task augmentation labels (style='task_aug')."""

    @property
    def annotation_type(self) -> str:
        return "task_aug"

    def extract_splits(
        self,
        dataset_meta: dict[str, Any],
        annotations: dict[int, list[dict[str, Any]]],
        **kwargs,
    ) -> dict[str, list[EpisodeSegment]]:
        splits: dict[str, list[EpisodeSegment]] = {}
        fps = float(dataset_meta.get("fps", 30.0))
        total_episodes = int(dataset_meta.get("total_episodes", len(annotations)))
        episode_lengths = dataset_meta.get("episode_lengths", {})

        for ep_idx in range(total_episodes):
            ep_length = episode_lengths.get(ep_idx, int(dataset_meta.get("default_length", 300)))
            ep_duration = ep_length / fps

            atoms = annotations.get(ep_idx, [])
            aug_atoms = [a for a in atoms if a.get("style") == "task_aug" and a.get("content")]

            if not aug_atoms:
                split_name = "standard"
                label = "standard"
            else:
                label = str(aug_atoms[0]["content"]).strip()
                split_name = sanitize_name(label)

            seg = EpisodeSegment(
                source_episode_index=ep_idx,
                start_frame=0,
                end_frame=ep_length,
                start_timestamp=0.0,
                end_timestamp=ep_duration,
                label=label,
                split_name=split_name,
                annotation_type="task_aug",
                metadata={"atoms": atoms},
            )
            splits.setdefault(split_name, []).append(seg)

        return splits


# ------------------------------------------------------------------------------
# 3. Plan Splitter
# ------------------------------------------------------------------------------


@register_splitter("plan")
class PlanSplitter(BaseAnnotationSplitter):
    """Splits episodes by high-level plan steps (style='plan')."""

    @property
    def annotation_type(self) -> str:
        return "plan"

    def extract_splits(
        self,
        dataset_meta: dict[str, Any],
        annotations: dict[int, list[dict[str, Any]]],
        min_frames: int = 5,
        **kwargs,
    ) -> dict[str, list[EpisodeSegment]]:
        splits: dict[str, list[EpisodeSegment]] = {}
        fps = float(dataset_meta.get("fps", 30.0))
        total_episodes = int(dataset_meta.get("total_episodes", len(annotations)))
        episode_lengths = dataset_meta.get("episode_lengths", {})

        for ep_idx in range(total_episodes):
            ep_length = episode_lengths.get(ep_idx, int(dataset_meta.get("default_length", 300)))
            ep_duration = ep_length / fps

            atoms = annotations.get(ep_idx, [])
            plan_atoms = [a for a in atoms if a.get("style") == "plan" and a.get("content")]
            if not plan_atoms:
                continue

            plan_atoms.sort(key=lambda a: float(a.get("timestamp", 0.0)))
            for i, atom in enumerate(plan_atoms):
                label = str(atom["content"]).strip()
                start_ts = float(atom.get("timestamp", 0.0))
                end_ts = (
                    float(plan_atoms[i + 1].get("timestamp", ep_duration))
                    if i + 1 < len(plan_atoms)
                    else ep_duration
                )

                start_frame = max(0, min(int(round(start_ts * fps)), ep_length))
                end_frame = max(start_frame, min(int(round(end_ts * fps)), ep_length))

                if end_frame - start_frame < min_frames:
                    continue

                split_slug = sanitize_name(label)
                seg = EpisodeSegment(
                    source_episode_index=ep_idx,
                    start_frame=start_frame,
                    end_frame=end_frame,
                    start_timestamp=start_ts,
                    end_timestamp=end_ts,
                    label=label,
                    split_name=split_slug,
                    annotation_type="plan",
                    metadata={"plan_index": i},
                )
                splits.setdefault(split_slug, []).append(seg)

        return splits


# ------------------------------------------------------------------------------
# 4. VQA Splitter
# ------------------------------------------------------------------------------


@register_splitter("vqa")
class VQASplitter(BaseAnnotationSplitter):
    """Splits episodes into windows around VQA events (style='vqa')."""

    @property
    def annotation_type(self) -> str:
        return "vqa"

    def extract_splits(
        self,
        dataset_meta: dict[str, Any],
        annotations: dict[int, list[dict[str, Any]]],
        vqa_window_s: float = 2.0,
        **kwargs,
    ) -> dict[str, list[EpisodeSegment]]:
        splits: dict[str, list[EpisodeSegment]] = {}
        fps = float(dataset_meta.get("fps", 30.0))
        total_episodes = int(dataset_meta.get("total_episodes", len(annotations)))
        episode_lengths = dataset_meta.get("episode_lengths", {})

        for ep_idx in range(total_episodes):
            ep_length = episode_lengths.get(ep_idx, int(dataset_meta.get("default_length", 300)))
            ep_duration = ep_length / fps

            atoms = annotations.get(ep_idx, [])
            vqa_atoms = [a for a in atoms if a.get("style") == "vqa" and a.get("content")]

            for atom in vqa_atoms:
                ts = float(atom.get("timestamp", 0.0))
                start_ts = max(0.0, ts - vqa_window_s / 2.0)
                end_ts = min(ep_duration, ts + vqa_window_s / 2.0)

                start_frame = max(0, min(int(round(start_ts * fps)), ep_length))
                end_frame = max(start_frame, min(int(round(end_ts * fps)), ep_length))

                label = f"vqa_{atom.get('camera') or 'general'}"
                split_slug = sanitize_name(label)

                seg = EpisodeSegment(
                    source_episode_index=ep_idx,
                    start_frame=start_frame,
                    end_frame=end_frame,
                    start_timestamp=start_ts,
                    end_timestamp=end_ts,
                    label=label,
                    split_name=split_slug,
                    annotation_type="vqa",
                    metadata={"vqa_atom": atom},
                )
                splits.setdefault(split_slug, []).append(seg)

        return splits


# ------------------------------------------------------------------------------
# 5. Speech Splitter
# ------------------------------------------------------------------------------


@register_splitter("speech")
class SpeechSplitter(BaseAnnotationSplitter):
    """Splits episodes into windows around speech / dialogue atoms."""

    @property
    def annotation_type(self) -> str:
        return "speech"

    def extract_splits(
        self,
        dataset_meta: dict[str, Any],
        annotations: dict[int, list[dict[str, Any]]],
        speech_window_s: float = 3.0,
        **kwargs,
    ) -> dict[str, list[EpisodeSegment]]:
        splits: dict[str, list[EpisodeSegment]] = {}
        fps = float(dataset_meta.get("fps", 30.0))
        total_episodes = int(dataset_meta.get("total_episodes", len(annotations)))
        episode_lengths = dataset_meta.get("episode_lengths", {})

        for ep_idx in range(total_episodes):
            ep_length = episode_lengths.get(ep_idx, int(dataset_meta.get("default_length", 300)))
            ep_duration = ep_length / fps

            atoms = annotations.get(ep_idx, [])
            speech_atoms = [
                a
                for a in atoms
                if a.get("style") == "interjection"
                or (
                    a.get("tool_calls")
                    and any(tc.get("function", {}).get("name") == "say" for tc in a["tool_calls"])
                )
            ]

            for atom in speech_atoms:
                ts = float(atom.get("timestamp", 0.0))
                start_ts = max(0.0, ts - 1.0)
                end_ts = min(ep_duration, ts + speech_window_s)

                start_frame = max(0, min(int(round(start_ts * fps)), ep_length))
                end_frame = max(start_frame, min(int(round(end_ts * fps)), ep_length))

                content = str(atom.get("content") or "speech_utterance")
                split_slug = sanitize_name(content[:30])

                seg = EpisodeSegment(
                    source_episode_index=ep_idx,
                    start_frame=start_frame,
                    end_frame=end_frame,
                    start_timestamp=start_ts,
                    end_timestamp=end_ts,
                    label=content,
                    split_name=split_slug,
                    annotation_type="speech",
                    metadata={"speech_atom": atom},
                )
                splits.setdefault(split_slug, []).append(seg)

        return splits


# ==============================================================================
# Helper for Extracting Dataset Metadata without importing lerobot
# ==============================================================================


def read_dataset_metadata(dataset_root: Path) -> dict[str, Any]:
    """Read metadata dictionary from dataset directory."""
    meta: dict[str, Any] = {
        "fps": 30.0,
        "total_episodes": 0,
        "episode_lengths": {},
        "robot_type": "unknown",
        "features": {},
    }

    info_path = dataset_root / "meta" / "info.json"
    if info_path.exists():
        try:
            with open(info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
                meta["fps"] = float(info.get("fps", 30.0))
                meta["total_episodes"] = int(info.get("total_episodes", 0))
                meta["robot_type"] = info.get("robot_type", "unknown")
                meta["features"] = info.get("features", {})
        except Exception:
            pass

    # Read episode lengths from meta/episodes/ if available
    episodes_dir = dataset_root / "meta" / "episodes"
    if episodes_dir.exists():
        parquet_files = sorted(episodes_dir.rglob("*.parquet"))
        if parquet_files:
            try:
                episodes_df = pd.concat([pd.read_parquet(p) for p in parquet_files], ignore_index=True)
                for idx, row in episodes_df.iterrows():
                    ep_idx = int(row.get("episode_index", idx))
                    if "length" in row:
                        meta["episode_lengths"][ep_idx] = int(row["length"])
                if meta["total_episodes"] == 0:
                    meta["total_episodes"] = len(meta["episode_lengths"])
            except Exception:
                pass

    # Read from data parquet if episode_lengths not populated
    if not meta["episode_lengths"]:
        data_parquets = sorted(dataset_root.glob("data/**/*.parquet"))
        for p in data_parquets:
            try:
                df = pd.read_parquet(p)
                if "episode_index" in df.columns:
                    for ep_idx, group in df.groupby("episode_index"):
                        meta["episode_lengths"][int(ep_idx)] = len(group)
            except Exception:
                pass
        if meta["total_episodes"] == 0 and meta["episode_lengths"]:
            meta["total_episodes"] = len(meta["episode_lengths"])

    return meta


# ==============================================================================
# Subdataset Creation & HF Push
# ==============================================================================


def create_subdataset(
    src_root: Path,
    segments: list[EpisodeSegment],
    output_dir: Path,
    repo_id: str,
    vcodec: str = "libsvtav1",
    overwrite: bool = False,
    drop_depth: bool = False,
    drop_ee: bool = False,
) -> Path:
    """Build a new subdataset directory containing only the specified episode segments."""
    if output_dir.exists():
        if overwrite:
            shutil.rmtree(output_dir)
        else:
            raise FileExistsError(f"Output directory '{output_dir}' already exists. Use overwrite=True.")

    output_dir.mkdir(parents=True, exist_ok=True)
    meta_src = read_dataset_metadata(src_root)
    fps = meta_src["fps"]

    # Try LeRobotDataset API if available and video decoding is needed
    has_videos = bool(list((src_root / "videos").glob("*"))) if (src_root / "videos").exists() else False

    if has_videos:
        try:
            from lerobot.datasets.lerobot_dataset import LeRobotDataset
            from lerobot.datasets.video_utils import decode_video_frames
            import torch

            # Load src dataset safely
            sanitize_dataset_metadata(src_root)
            src_ds = LeRobotDataset(str(src_root), root=src_root)

            data_features = {}
            for k, v in src_ds.meta.features.items():
                if k in DEFAULT_IGNORE_FEATURES:
                    continue
                if drop_depth and "depth" in k.lower():
                    continue
                feat_copy = dict(v)
                if drop_ee and k in {"observation.state", "action"}:
                    feat_copy["shape"] = (6,)
                    if "names" in feat_copy and feat_copy["names"] and len(feat_copy["names"]) > 6:
                        feat_copy["names"] = feat_copy["names"][:6]
                data_features[k] = feat_copy

            video_keys_to_process = [
                k for k in src_ds.meta.video_keys if not (drop_depth and "depth" in k.lower())
            ]
            use_videos = len(video_keys_to_process) > 0

            new_ds = LeRobotDataset.create(
                repo_id=repo_id,
                fps=src_ds.meta.fps,
                root=output_dir,
                robot_type=src_ds.meta.robot_type,
                features=data_features,
                use_videos=use_videos,
                image_writer_processes=0,
                image_writer_threads=4 if use_videos else 0,
                vcodec=vcodec,
            )

            new_annotations: dict[str, dict[str, Any]] = {}

            for new_ep_idx, segment in enumerate(segments):
                src_ep_idx = segment.source_episode_index
                src_ep_meta = src_ds.meta.episodes[src_ep_idx]
                ep_base_from_idx = int(src_ep_meta["dataset_from_index"])

                num_frames = segment.num_frames
                if num_frames <= 0:
                    continue

                seg_from_idx = ep_base_from_idx + segment.start_frame
                seg_to_idx = ep_base_from_idx + segment.end_frame

                hf_slice = src_ds.hf_dataset.select(range(seg_from_idx, seg_to_idx))

                video_data: dict[str, np.ndarray] = {}
                if use_videos:
                    for vid_key in video_keys_to_process:
                        from_ts = float(src_ep_meta[f"videos/{vid_key}/from_timestamp"])
                        shifted_ts = [
                            from_ts + (segment.start_frame + i) * (1.0 / fps) for i in range(num_frames)
                        ]
                        video_file_rel = src_ds.meta.get_video_file_path(src_ep_idx, vid_key)
                        video_path = src_ds.root / video_file_rel

                        frames_tensor = decode_video_frames(
                            video_path, shifted_ts, src_ds.tolerance_s, src_ds.video_backend
                        )
                        frames_np = (
                            (frames_tensor * 255.0)
                            .clamp(0, 255)
                            .to(torch.uint8)
                            .permute(0, 2, 3, 1)
                            .cpu()
                            .numpy()
                        )
                        video_data[vid_key] = frames_np

                for i in range(num_frames):
                    frame = {}
                    for k in data_features:
                        if k in video_data:
                            frame[k] = video_data[k][i]
                        else:
                            val = hf_slice[i][k]
                            if drop_ee and k in {"observation.state", "action"}:
                                if isinstance(val, (list, np.ndarray)):
                                    val = val[:6]
                            frame[k] = val
                    frame["task"] = segment.label
                    new_ds.add_frame(frame)

                new_ds.save_episode()
                new_atoms = [
                    {
                        "role": "assistant",
                        "content": segment.label,
                        "style": segment.annotation_type,
                        "timestamp": 0.0,
                        "camera": None,
                        "tool_calls": None,
                    }
                ]
                for ev in segment.metadata.get("events", []):
                    new_atoms.append(ev)
                new_annotations[str(new_ep_idx)] = {"atoms": new_atoms}

            new_ds.finalize()

            ann_file_path = output_dir / "meta" / "lerobot_annotations.json"
            ann_payload = {
                "version": 2,
                "schema": {
                    "persistent_styles": ["memory", "plan", "subtask", "task_aug"],
                    "event_styles": ["interjection", "vqa"],
                },
                "episodes": new_annotations,
            }
            with open(ann_file_path, "w", encoding="utf-8") as f:
                json.dump(ann_payload, f, indent=2)

            return output_dir
        except Exception as e:
            logger.warning(f"LeRobotDataset slicing encountered error: {e}. Falling back to tabular slice.")

    # Fallback / Tabular slicing mode:
    # Slices parquet tables and copies/updates metadata directly
    data_dir = output_dir / "data" / "chunk-000"
    data_dir.mkdir(parents=True, exist_ok=True)
    meta_dir = output_dir / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    src_parquets = sorted(src_root.glob("data/**/*.parquet"))
    if not src_parquets:
        src_parquets = sorted(src_root.glob("**/*.parquet"))
        src_parquets = [p for p in src_parquets if "meta" not in Path(p).parts]

    all_dfs = [pd.read_parquet(p) for p in src_parquets]
    full_df = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

    sliced_frames: list[pd.DataFrame] = []
    new_annotations = {}
    current_frame_idx = 0

    for new_ep_idx, segment in enumerate(segments):
        src_ep = segment.source_episode_index
        if "episode_index" in full_df.columns:
            ep_subset = full_df[full_df["episode_index"] == src_ep]
        else:
            ep_subset = full_df

        sub_slice = ep_subset.iloc[segment.start_frame : segment.end_frame].copy()
        if len(sub_slice) == 0:
            continue

        sub_slice["episode_index"] = new_ep_idx
        sub_slice["frame_index"] = range(len(sub_slice))
        sub_slice["timestamp"] = [i / fps for i in range(len(sub_slice))]
        if "index" in sub_slice.columns:
            sub_slice["index"] = range(current_frame_idx, current_frame_idx + len(sub_slice))
        current_frame_idx += len(sub_slice)
        sub_slice["task"] = segment.label

        if drop_depth:
            depth_cols = [c for c in sub_slice.columns if "depth" in c.lower()]
            if depth_cols:
                sub_slice = sub_slice.drop(columns=depth_cols)

        if drop_ee:
            for col in ["observation.state", "action"]:
                if col in sub_slice.columns:
                    sub_slice[col] = sub_slice[col].apply(lambda x: list(x)[:6] if hasattr(x, "__len__") and len(x) >= 6 else x)

        sliced_frames.append(sub_slice)
        new_annotations[str(new_ep_idx)] = {
            "atoms": [
                {
                    "role": "assistant",
                    "content": segment.label,
                    "style": segment.annotation_type,
                    "timestamp": 0.0,
                    "camera": None,
                    "tool_calls": None,
                }
            ]
        }

    if sliced_frames:
        out_table = pd.concat(sliced_frames, ignore_index=True)
        out_table.to_parquet(data_dir / "episode_0.parquet", index=False)

    # Info.json
    info = dict(meta_src)
    info["total_episodes"] = len(sliced_frames)
    info["total_frames"] = current_frame_idx
    info["splits"] = {"train": f"0:{len(sliced_frames)}"}
    info["repo_id"] = repo_id
    with open(meta_dir / "info.json", "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)

    # Annotations
    ann_file_path = meta_dir / "lerobot_annotations.json"
    ann_payload = {
        "version": 2,
        "schema": {
            "persistent_styles": ["memory", "plan", "subtask", "task_aug"],
            "event_styles": ["interjection", "vqa"],
        },
        "episodes": new_annotations,
    }
    with open(ann_file_path, "w", encoding="utf-8") as f:
        json.dump(ann_payload, f, indent=2)

    return output_dir


def push_subdataset_to_hub(
    local_dir: Path,
    repo_id: str,
    hf_token: Optional[str] = None,
    private: bool = False,
    commit_message: Optional[str] = None,
) -> str:
    """Upload a subdataset folder to Hugging Face Hub."""
    from huggingface_hub import HfApi

    token = hf_token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    api = HfApi(token=token)
    api.create_repo(repo_id=repo_id, repo_type="dataset", private=private, exist_ok=True)
    msg = commit_message or f"Upload subdataset {repo_id} split by annotations"
    api.upload_folder(
        folder_path=str(local_dir),
        repo_id=repo_id,
        repo_type="dataset",
        commit_message=msg,
    )
    return f"https://huggingface.co/datasets/{repo_id}"


# ==============================================================================
# High-Level Split API
# ==============================================================================


def split_dataset(
    dataset_path: str | Path,
    output_dir: str | Path,
    annotation_type: str = "subtask",
    target_subtasks: Optional[list[str]] = None,
    annotations_file: Optional[str | Path] = None,
    min_frames: int = 5,
    min_duration_s: float = 0.1,
    vcodec: str = "libsvtav1",
    overwrite: bool = False,
    drop_depth: bool = False,
    drop_ee: bool = False,
    push_to_hub: bool = False,
    hub_repo_prefix: Optional[str] = None,
    hub_repo_id: Optional[str] = None,
    hf_token: Optional[str] = None,
    private: bool = False,
    dry_run: bool = False,
) -> list[SplitResult]:
    """Split a dataset into subdatasets based on visualizer annotations.

    Returns:
        List of SplitResult objects.
    """
    input_str = str(dataset_path).strip()
    is_remote = not Path(input_str).exists() and ("/" in input_str)
    temp_download_dir: Optional[Path] = None

    if is_remote:
        from huggingface_hub import snapshot_download

        temp_download_dir = Path("./temp_split_download")
        if temp_download_dir.exists():
            shutil.rmtree(temp_download_dir)
        temp_download_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Downloading dataset from Hugging Face Hub: {input_str}...")
        snapshot_download(repo_id=input_str, repo_type="dataset", local_dir=str(temp_download_dir))
        src_root = temp_download_dir
    else:
        src_root = Path(input_str).resolve()
        if not src_root.exists():
            raise FileNotFoundError(f"Source dataset directory does not exist: {input_str}")

    custom_ann = Path(annotations_file).resolve() if annotations_file else None
    annotations = load_dataset_annotations(src_root, custom_ann)
    dataset_meta = read_dataset_metadata(src_root)

    splitter = get_splitter(annotation_type)
    splits_dict = splitter.extract_splits(
        dataset_meta=dataset_meta,
        annotations=annotations,
        target_subtasks=target_subtasks,
        min_frames=min_frames,
        min_duration_s=min_duration_s,
    )

    out_base = Path(output_dir).resolve()
    results: list[SplitResult] = []

    for split_slug, segments in splits_dict.items():
        if not segments:
            continue

        label = segments[0].label
        split_dir = out_base / split_slug

        # Determine Hub repo ID if uploading
        dest_repo_id: Optional[str] = None
        if push_to_hub:
            if hub_repo_id:
                dest_repo_id = hub_repo_id
            elif hub_repo_prefix:
                dest_repo_id = f"{hub_repo_prefix.rstrip('/')}/{split_slug}"
            else:
                dest_repo_id = f"{Path(input_str).name}-{split_slug}"

        res = SplitResult(
            split_name=split_slug,
            label=label,
            annotation_type=annotation_type,
            segments=segments,
            local_output_path=split_dir if not dry_run else None,
            hub_repo_id=dest_repo_id if push_to_hub and not dry_run else None,
        )

        if not dry_run:
            sub_repo_name = dest_repo_id or f"local/{split_slug}"
            create_subdataset(
                src_root=src_root,
                segments=segments,
                output_dir=split_dir,
                repo_id=sub_repo_name,
                vcodec=vcodec,
                overwrite=overwrite,
                drop_depth=drop_depth,
                drop_ee=drop_ee,
            )

            if push_to_hub and dest_repo_id:
                push_subdataset_to_hub(
                    local_dir=split_dir,
                    repo_id=dest_repo_id,
                    hf_token=hf_token,
                    private=private,
                )

        results.append(res)

    if temp_download_dir and temp_download_dir.exists():
        shutil.rmtree(temp_download_dir, ignore_errors=True)

    return results


def display_split_results(results: list[SplitResult], dry_run: bool = False) -> None:
    """Render a Rich formatted summary table of split results."""
    title_suffix = " (DRY RUN)" if dry_run else ""
    table = Table(title=f"[bold bright_blue]⚡ Dataset Split Results{title_suffix} ⚡[/bold bright_blue]")
    table.add_column("Split Slug", style="cyan")
    table.add_column("Label / Instruction", style="white")
    table.add_column("Episodes", justify="right", style="green")
    table.add_column("Total Frames", justify="right", style="magenta")
    table.add_column("Destination", style="dim")

    for res in results:
        dest_str = str(res.local_output_path) if res.local_output_path else "[yellow]Dry Run Preview[/yellow]"
        if res.hub_repo_id:
            dest_str += f" → [bold green]{res.hub_repo_id}[/bold green]"
        table.add_row(
            res.split_name,
            res.label[:40],
            str(res.num_episodes),
            str(res.total_frames),
            dest_str,
        )

    console.print(table)
