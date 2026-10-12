"""Annotation loading, sanitization, and inspection utilities for LeRobot datasets.

Supports the canonical format used by lerobot-dataset-viz / visualizer:
- meta/lerobot_annotations.json (v2 schema with atom arrays and legacy v1 schema)
- embedded parquet language columns (language_persistent, language_events)
"""

from __future__ import annotations

import glob
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from rich.panel import Panel
from rich.table import Table

from clirobot.ui.console import console

logger = logging.getLogger("clirobot.dataset.annotations")


@dataclass
class AnnotationSummary:
    """Statistical summary of annotations discovered in a dataset."""

    repo_id_or_path: str
    total_episodes: int
    annotated_episodes: int
    fps: float = 30.0
    by_style: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    episodes_map: dict[int, list[dict[str, Any]]] = field(default_factory=dict)

    @property
    def has_annotations(self) -> bool:
        return self.annotated_episodes > 0


def sanitize_name(name: str) -> str:
    """Convert an arbitrary annotation label into a filesystem- and repo-safe slug."""
    import re
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "unnamed_split"


def load_annotations_from_json(path: Path) -> dict[int, list[dict[str, Any]]]:
    """Parse meta/lerobot_annotations.json supporting both v2 and legacy v1 schemas.

    Returns:
        dict mapping episode_index -> list of atom dicts
    """
    if not path.is_file():
        raise FileNotFoundError(f"Annotations file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    episodes_data = data.get("episodes", {})
    parsed_atoms: dict[int, list[dict[str, Any]]] = {}

    for ep_key, ep_content in episodes_data.items():
        try:
            ep_idx = int(ep_key)
        except ValueError:
            continue

        atoms: list[dict[str, Any]] = []

        # Case 1: v2 schema with "atoms" array
        if "atoms" in ep_content and isinstance(ep_content["atoms"], list):
            for atom in ep_content["atoms"]:
                if isinstance(atom, dict):
                    atoms.append(
                        {
                            "role": atom.get("role", "assistant"),
                            "content": atom.get("content"),
                            "style": atom.get("style"),
                            "timestamp": float(atom.get("timestamp", 0.0)),
                            "camera": atom.get("camera"),
                            "tool_calls": atom.get("tool_calls"),
                        }
                    )

        # Case 2: legacy v1 schema with "subtasks" and "high_levels"
        else:
            for sub in ep_content.get("subtasks", []):
                if isinstance(sub, dict) and "label" in sub:
                    atoms.append(
                        {
                            "role": "assistant",
                            "content": str(sub["label"]),
                            "style": "subtask",
                            "timestamp": float(sub.get("start", 0.0)),
                            "_legacy_end": float(sub.get("end", 0.0)) if "end" in sub else None,
                            "camera": None,
                            "tool_calls": None,
                        }
                    )
            for hl in ep_content.get("high_levels", []):
                if isinstance(hl, dict):
                    ts = float(hl.get("start", 0.0))
                    if hl.get("user_prompt"):
                        atoms.append(
                            {
                                "role": "user",
                                "content": str(hl["user_prompt"]),
                                "style": "interjection",
                                "timestamp": ts,
                                "camera": None,
                                "tool_calls": None,
                            }
                        )
                    if hl.get("robot_utterance"):
                        atoms.append(
                            {
                                "role": "assistant",
                                "content": None,
                                "style": None,
                                "timestamp": ts,
                                "camera": None,
                                "tool_calls": [
                                    {
                                        "type": "function",
                                        "function": {
                                            "name": "say",
                                            "arguments": {"text": str(hl["robot_utterance"])},
                                        },
                                    }
                                ],
                            }
                        )

        # Sort atoms chronologically
        atoms.sort(key=lambda a: (float(a.get("timestamp", 0.0)), str(a.get("style") or "")))
        parsed_atoms[ep_idx] = atoms

    return parsed_atoms


def load_annotations_from_parquet(dataset_root: Path) -> dict[int, list[dict[str, Any]]]:
    """Extract language annotations if embedded in parquet columns (language_persistent / language_events)."""
    parquet_files = sorted(glob.glob(str(dataset_root / "data" / "**" / "*.parquet"), recursive=True))
    if not parquet_files:
        return {}

    parsed_atoms: dict[int, list[dict[str, Any]]] = {}

    for file_path in parquet_files:
        try:
            df = pd.read_parquet(file_path)
        except Exception as e:
            logger.debug(f"Failed to read parquet {file_path}: {e}")
            continue

        if "episode_index" not in df.columns:
            continue

        has_persistent = "language_persistent" in df.columns
        has_events = "language_events" in df.columns

        if not (has_persistent or has_events):
            continue

        for ep_idx, group in df.groupby("episode_index"):
            ep_idx = int(ep_idx)
            atoms_list = parsed_atoms.setdefault(ep_idx, [])
            seen_hashes = {json.dumps(a, sort_keys=True, default=str) for a in atoms_list}

            # Persistent language items (broadcast across episode)
            if has_persistent:
                first_row = group["language_persistent"].iloc[0]
                if first_row is not None and hasattr(first_row, "__iter__"):
                    for item in first_row:
                        if isinstance(item, dict):
                            h = json.dumps(item, sort_keys=True, default=str)
                            if h not in seen_hashes:
                                seen_hashes.add(h)
                                atoms_list.append(dict(item))

            # Event language items (on specific frames)
            if has_events:
                for _, row in group.iterrows():
                    ev_items = row["language_events"]
                    frame_ts = float(row.get("timestamp", 0.0))
                    if ev_items is not None and hasattr(ev_items, "__iter__"):
                        for item in ev_items:
                            if isinstance(item, dict):
                                atom = dict(item)
                                if "timestamp" not in atom or atom["timestamp"] is None:
                                    atom["timestamp"] = frame_ts
                                h = json.dumps(atom, sort_keys=True, default=str)
                                if h not in seen_hashes:
                                    seen_hashes.add(h)
                                    atoms_list.append(atom)

    for ep_idx in parsed_atoms:
        parsed_atoms[ep_idx].sort(key=lambda a: (float(a.get("timestamp", 0.0)), str(a.get("style") or "")))

    return parsed_atoms


def load_dataset_annotations(
    dataset_root: Path,
    custom_annotations_path: Optional[Path] = None,
) -> dict[int, list[dict[str, Any]]]:
    """Primary loader for annotations: checks custom path, meta/lerobot_annotations.json, and parquet."""
    # 1. Custom path if explicitly provided
    if custom_annotations_path:
        return load_annotations_from_json(custom_annotations_path)

    # 2. Standard visualizer path: meta/lerobot_annotations.json
    default_meta_ann = dataset_root / "meta" / "lerobot_annotations.json"
    if default_meta_ann.exists():
        return load_annotations_from_json(default_meta_ann)

    # 3. Embedded parquet language columns
    parquet_ann = load_annotations_from_parquet(dataset_root)
    if parquet_ann:
        return parquet_ann

    return {}


def sanitize_dataset_metadata(dataset_root: Path) -> bool:
    """Sanitize metadata in local dataset directory for safe LeRobot loading.

    1. Removes any 'language' dtype features that cause schema mismatch.
    2. Recovers total_episodes, total_frames, and splits from meta/episodes/ or data/ if info.json has 0.
    3. Ensures tasks.parquet exists if total_tasks is missing.
    """
    info_path = dataset_root / "meta" / "info.json"
    if not info_path.is_file():
        return False

    try:
        with open(info_path, "r", encoding="utf-8") as f:
            info = json.load(f)
    except Exception as e:
        logger.warning(f"Could not read info.json for sanitization: {e}")
        return False

    modified = False
    features = info.get("features", {})

    # 1. Remove non-standard language features
    keys_to_remove = [
        k
        for k, v in features.items()
        if isinstance(v, dict)
        and (v.get("dtype") == "language" or k in {"language_persistent", "language_events", "tools"})
    ]
    for k in keys_to_remove:
        features.pop(k, None)
        modified = True

    # 2. Fix total_episodes / total_frames if 0 or missing
    if info.get("total_episodes", 0) == 0:
        episodes_dir = dataset_root / "meta" / "episodes"
        if episodes_dir.exists():
            parquet_files = sorted(episodes_dir.rglob("*.parquet"))
            if parquet_files:
                try:
                    episodes_df = pd.concat([pd.read_parquet(p) for p in parquet_files], ignore_index=True)
                    num_episodes = len(episodes_df)
                    num_frames = int(episodes_df["length"].sum()) if "length" in episodes_df.columns else 0
                    info["total_episodes"] = num_episodes
                    info["total_frames"] = num_frames
                    info["splits"] = {"train": f"0:{num_episodes}"}
                    modified = True
                except Exception as e:
                    logger.debug(f"Failed to infer episode counts from episodes dir: {e}")

        if info.get("total_episodes", 0) == 0:
            data_parquet = sorted(dataset_root.glob("data/**/*.parquet"))
            if data_parquet:
                try:
                    df = pd.concat([pd.read_parquet(p) for p in data_parquet], ignore_index=True)
                    if "episode_index" in df.columns:
                        unique_eps = df["episode_index"].nunique()
                        info["total_episodes"] = int(unique_eps)
                        info["total_frames"] = len(df)
                        info["splits"] = {"train": f"0:{unique_eps}"}
                        modified = True
                except Exception as e:
                    logger.debug(f"Failed to infer episode counts from data parquet: {e}")

    # 3. Ensure tasks.parquet exists
    tasks_path = dataset_root / "meta" / "tasks.parquet"
    if not tasks_path.is_file() and info.get("total_tasks", 0) == 0:
        try:
            default_df = pd.DataFrame({"task": ["default_task"]})
            default_df.index = default_df.index.rename("__index_level_0__")
            default_df.to_parquet(tasks_path)
            info["total_tasks"] = 1
            modified = True
        except Exception as e:
            logger.debug(f"Could not create placeholder tasks.parquet: {e}")

    if modified:
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)

    return modified


def inspect_annotations(
    dataset_root: Path,
    custom_annotations_path: Optional[Path] = None,
) -> AnnotationSummary:
    """Analyze and generate statistical summary of annotations."""
    # Read total_episodes and fps from info.json if present
    total_episodes = 0
    fps = 30.0
    info_path = dataset_root / "meta" / "info.json"
    if info_path.exists():
        try:
            with open(info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
                total_episodes = int(info.get("total_episodes", 0))
                fps = float(info.get("fps", 30.0))
        except Exception:
            pass

    annotations = load_dataset_annotations(dataset_root, custom_annotations_path)

    if total_episodes == 0 and annotations:
        total_episodes = max(annotations.keys()) + 1 if annotations else 0

    by_style: dict[str, dict[str, list[float]]] = {}
    episodes_with_ann = set()

    for ep_idx, atoms in annotations.items():
        if atoms:
            episodes_with_ann.add(ep_idx)
        for atom in atoms:
            style = str(atom.get("style") or ("speech" if atom.get("tool_calls") else "unknown"))
            content = str(atom.get("content") or "(tool_call / action)")
            by_style.setdefault(style, {}).setdefault(content, []).append(float(atom.get("timestamp", 0.0)))

    return AnnotationSummary(
        repo_id_or_path=str(dataset_root),
        total_episodes=total_episodes,
        annotated_episodes=len(episodes_with_ann),
        fps=fps,
        by_style=by_style,
        episodes_map=annotations,
    )


def display_annotation_summary(summary: AnnotationSummary, title: str | None = None) -> None:
    """Render a Rich formatted summary table of annotations."""
    summary_title = title or f"Annotation Inspection: {Path(summary.repo_id_or_path).name}"

    if not summary.has_annotations:
        console.print(
            Panel(
                f"[yellow]No visualizer annotations found in dataset[/yellow]\n"
                f"[dim]Dataset: {summary.repo_id_or_path} | Total Episodes: {summary.total_episodes}[/dim]",
                title=f"[bold cyan]🔍 {summary_title}[/bold cyan]",
                border_style="yellow",
            )
        )
        return

    pct = (
        (summary.annotated_episodes / summary.total_episodes * 100.0)
        if summary.total_episodes > 0
        else 100.0
    )

    overview_table = Table.grid(padding=(0, 2))
    overview_table.add_column(style="bold cyan", width=22)
    overview_table.add_column(style="white")
    overview_table.add_row("Total Episodes:", f"[bold]{summary.total_episodes}[/bold]")
    overview_table.add_row(
        "Annotated Episodes:",
        f"[bold green]{summary.annotated_episodes}[/bold green] ({pct:.1f}% coverage)",
    )
    overview_table.add_row("Recording FPS:", f"[green]{summary.fps:.1f}[/green]")
    overview_table.add_row("Annotation Styles:", f"[yellow]{', '.join(sorted(summary.by_style.keys()))}[/yellow]")

    console.print(
        Panel(
            overview_table,
            title=f"[bold bright_blue]⚡ {summary_title} ⚡[/bold bright_blue]",
            border_style="bright_blue",
        )
    )

    for style, content_dict in sorted(summary.by_style.items()):
        table = Table(title=f"Style: [bold yellow]{style.upper()}[/bold yellow] ({len(content_dict)} unique labels)")
        table.add_column("Label / Content", style="cyan", no_wrap=False)
        table.add_column("Occurrences", justify="right", style="green")
        table.add_column("Avg Timestamp", justify="right", style="magenta")
        table.add_column("Min Ts", justify="right", style="dim")
        table.add_column("Max Ts", justify="right", style="dim")

        for label, timestamps in sorted(content_dict.items(), key=lambda x: len(x[1]), reverse=True):
            avg_ts = sum(timestamps) / len(timestamps) if timestamps else 0.0
            min_ts = min(timestamps) if timestamps else 0.0
            max_ts = max(timestamps) if timestamps else 0.0
            table.add_row(
                label,
                str(len(timestamps)),
                f"{avg_ts:.2f}s",
                f"{min_ts:.2f}s",
                f"{max_ts:.2f}s",
            )

        console.print(table)
        console.print()
