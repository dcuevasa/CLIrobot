"""Tests for dataset splitting and annotation parsing."""

import json
from pathlib import Path
import pandas as pd
import pytest

from clirobot.dataset.annotations import (
    load_annotations_from_json,
    load_dataset_annotations,
    inspect_annotations,
    sanitize_name,
)
from clirobot.dataset.split import (
    split_dataset,
    get_splitter,
    list_splitters,
    SubtaskSplitter,
    TaskAugSplitter,
    PlanSplitter,
    VQASplitter,
    SpeechSplitter,
)


def test_sanitize_name():
    assert sanitize_name("Pick up coffee pod!") == "pick_up_coffee_pod"
    assert sanitize_name("  Grab the Blue Block (v1)  ") == "grab_the_blue_block_v1"
    assert sanitize_name("---") == "unnamed_split"


def test_load_annotations_v2_and_v1(tmp_path: Path):
    # Test v2 schema
    v2_data = {
        "version": 2,
        "episodes": {
            "0": {
                "atoms": [
                    {"style": "subtask", "content": "pick cup", "timestamp": 1.5},
                    {"style": "vqa", "content": "where is cup", "timestamp": 2.0},
                ]
            }
        },
    }
    v2_path = tmp_path / "v2.json"
    v2_path.write_text(json.dumps(v2_data))

    atoms_v2 = load_annotations_from_json(v2_path)
    assert 0 in atoms_v2
    assert len(atoms_v2[0]) == 2
    assert atoms_v2[0][0]["content"] == "pick cup"

    # Test legacy v1 schema
    v1_data = {
        "episodes": {
            "0": {
                "subtasks": [
                    {"label": "open drawer", "start": 0.0, "end": 4.0},
                    {"label": "place object", "start": 4.0, "end": 8.0},
                ],
                "high_levels": [
                    {"user_prompt": "clean desk", "robot_utterance": "ok", "start": 0.0}
                ],
            }
        }
    }
    v1_path = tmp_path / "v1.json"
    v1_path.write_text(json.dumps(v1_data))

    atoms_v1 = load_annotations_from_json(v1_path)
    assert 0 in atoms_v1
    assert len(atoms_v1[0]) == 4  # 2 subtasks + 1 user prompt + 1 robot utterance
    subtasks = [a for a in atoms_v1[0] if a.get("style") == "subtask"]
    assert len(subtasks) == 2
    assert subtasks[0]["content"] == "open drawer"


def test_subtask_splitter():
    splitter = get_splitter("subtask")
    assert isinstance(splitter, SubtaskSplitter)
    assert "subtask" in list_splitters()

    dataset_meta = {
        "fps": 30.0,
        "total_episodes": 1,
        "episode_lengths": {0: 300},  # 10 seconds
    }
    annotations = {
        0: [
            {"style": "subtask", "content": "reach mug", "timestamp": 0.0},
            {"style": "subtask", "content": "grasp mug", "timestamp": 4.0},
            {"style": "subtask", "content": "lift mug", "timestamp": 7.0},
        ]
    }

    splits = splitter.extract_splits(dataset_meta, annotations)
    assert len(splits) == 3
    assert "reach_mug" in splits
    assert "grasp_mug" in splits
    assert "lift_mug" in splits

    seg1 = splits["reach_mug"][0]
    assert seg1.start_frame == 0
    assert seg1.end_frame == 120  # 4s * 30fps

    seg2 = splits["grasp_mug"][0]
    assert seg2.start_frame == 120
    assert seg2.end_frame == 210  # 7s * 30fps

    seg3 = splits["lift_mug"][0]
    assert seg3.start_frame == 210
    assert seg3.end_frame == 300  # 10s * 30fps


def test_split_dataset_end_to_end(tmp_path: Path):
    src_dir = tmp_path / "src_dataset"
    data_dir = src_dir / "data" / "chunk-000"
    meta_dir = src_dir / "meta"
    data_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    # 1 episode with 60 frames (2 seconds at 30fps)
    df = pd.DataFrame(
        {
            "frame_index": list(range(60)),
            "episode_index": [0] * 60,
            "timestamp": [i / 30.0 for i in range(60)],
            "observation.state": [[0.1] * 6] * 60,
            "action": [[1.0] * 6] * 60,
        }
    )
    df.to_parquet(data_dir / "episode_0.parquet", index=False)

    info_dict = {
        "repo_id": "test/source_dataset",
        "fps": 30.0,
        "total_episodes": 1,
        "total_frames": 60,
        "features": {
            "observation.state": {"dtype": "float32", "shape": [6]},
            "action": {"dtype": "float32", "shape": [6]},
        },
    }
    (meta_dir / "info.json").write_text(json.dumps(info_dict))

    ann_dict = {
        "version": 2,
        "episodes": {
            "0": {
                "atoms": [
                    {"style": "subtask", "content": "phase 1", "timestamp": 0.0},
                    {"style": "subtask", "content": "phase 2", "timestamp": 1.0},
                ]
            }
        },
    }
    (meta_dir / "lerobot_annotations.json").write_text(json.dumps(ann_dict))

    out_dir = tmp_path / "subdatasets"
    results = split_dataset(
        dataset_path=src_dir,
        output_dir=out_dir,
        annotation_type="subtask",
        min_frames=5,
    )

    assert len(results) == 2
    slugs = [r.split_name for r in results]
    assert "phase_1" in slugs
    assert "phase_2" in slugs

    # Check phase 1 output
    p1_dir = out_dir / "phase_1"
    assert (p1_dir / "meta" / "info.json").exists()
    assert (p1_dir / "meta" / "lerobot_annotations.json").exists()
    assert (p1_dir / "data" / "chunk-000" / "episode_0.parquet").exists()

    p1_df = pd.read_parquet(p1_dir / "data" / "chunk-000" / "episode_0.parquet")
    assert len(p1_df) == 30  # 1.0s at 30 fps
    assert p1_df["task"].iloc[0] == "phase 1"


def test_inspect_annotations(tmp_path: Path):
    ds_dir = tmp_path / "annotated_ds"
    meta_dir = ds_dir / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    info_dict = {"fps": 30.0, "total_episodes": 2}
    (meta_dir / "info.json").write_text(json.dumps(info_dict))

    ann_dict = {
        "version": 2,
        "episodes": {
            "0": {
                "atoms": [
                    {"style": "subtask", "content": "grasp", "timestamp": 0.5},
                    {"style": "vqa", "content": "where is tape", "timestamp": 1.0},
                ]
            },
            "1": {
                "atoms": [
                    {"style": "subtask", "content": "grasp", "timestamp": 0.6},
                ]
            },
        },
    }
    (meta_dir / "lerobot_annotations.json").write_text(json.dumps(ann_dict))

    summary = inspect_annotations(ds_dir)
    assert summary.total_episodes == 2
    assert summary.annotated_episodes == 2
    assert "subtask" in summary.by_style
    assert "vqa" in summary.by_style
    assert len(summary.by_style["subtask"]["grasp"]) == 2
