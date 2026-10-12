"""Tests for dataset pruning functionality."""

import json
from pathlib import Path
import pandas as pd
import pytest

from clirobot.dataset.prune import prune_dataset, PruneResult


def create_dummy_dataset(base_dir: Path) -> Path:
    """Helper to construct a mock LeRobot dataset structure."""
    data_dir = base_dir / "data" / "chunk-000"
    data_dir.mkdir(parents=True, exist_ok=True)

    videos_depth = base_dir / "videos" / "chunk-000" / "observation.images.wrist_depth"
    videos_laptop = base_dir / "videos" / "chunk-000" / "observation.images.laptop"
    videos_depth.mkdir(parents=True, exist_ok=True)
    videos_laptop.mkdir(parents=True, exist_ok=True)
    (videos_depth / "episode_0.mp4").write_text("dummy video")
    (videos_laptop / "episode_0.mp4").write_text("dummy video")

    # Parquet table
    df = pd.DataFrame(
        {
            "frame_index": [0, 1],
            "episode_index": [0, 0],
            "timestamp": [0.0, 0.033],
            "observation.images.laptop": [10, 11],
            "observation.images.wrist_depth": [20, 21],
            "observation.state": [
                [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
                [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
            ],
            "action": [
                [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
                [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
            ],
            "custom_temp": [35.5, 36.0],
        }
    )
    df.to_parquet(data_dir / "episode_0.parquet", index=False)

    # Place info.json in root (tests loose metadata normalization)
    info_dict = {
        "repo_id": "test/mock_dataset",
        "fps": 30.0,
        "total_episodes": 1,
        "total_frames": 2,
        "features": {
            "observation.images.laptop": {"dtype": "image"},
            "observation.images.wrist_depth": {"dtype": "image"},
            "observation.state": {
                "dtype": "float32",
                "shape": [8],
                "names": ["j1", "j2", "j3", "j4", "j5", "j6", "ee_x", "ee_y"],
            },
            "action": {
                "dtype": "float32",
                "shape": [8],
            },
            "custom_temp": {"dtype": "float32"},
        },
    }
    (base_dir / "info.json").write_text(json.dumps(info_dict))

    # Stats.json in meta/
    meta_dir = base_dir / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    stats_dict = {
        "observation.images.wrist_depth": {"mean": 20.5},
        "observation.state": {"mean": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]},
        "action": {"mean": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]},
        "custom_temp": {"mean": 35.75},
    }
    (meta_dir / "stats.json").write_text(json.dumps(stats_dict))

    return base_dir


def test_prune_drop_depth_and_drop_ee(tmp_path: Path):
    ds_dir = create_dummy_dataset(tmp_path)

    res = prune_dataset(
        dataset_path=ds_dir,
        drop_depth=True,
        drop_ee=True,
    )

    assert isinstance(res, PruneResult)
    assert res.modified_parquets == 1
    assert "observation.images.wrist_depth" in res.dropped_columns
    assert res.sliced_dof == 6

    # Verify parquet
    df = pd.read_parquet(ds_dir / "data" / "chunk-000" / "episode_0.parquet")
    assert "observation.images.wrist_depth" not in df.columns
    assert "observation.images.laptop" in df.columns
    assert len(df["observation.state"].iloc[0]) == 6
    assert len(df["action"].iloc[0]) == 6

    # Verify video folder deleted
    assert not (ds_dir / "videos" / "chunk-000" / "observation.images.wrist_depth").exists()
    assert (ds_dir / "videos" / "chunk-000" / "observation.images.laptop").exists()

    # Verify meta/info.json normalized and updated
    assert not (ds_dir / "info.json").exists()
    info_path = ds_dir / "meta" / "info.json"
    assert info_path.exists()
    with open(info_path) as f:
        info = json.load(f)
    assert "observation.images.wrist_depth" not in info["features"]
    assert info["features"]["observation.state"]["shape"] == [6]
    assert len(info["features"]["observation.state"]["names"]) == 6
    assert info["features"]["action"]["shape"] == [6]

    # Verify meta/stats.json updated
    stats_path = ds_dir / "meta" / "stats.json"
    assert stats_path.exists()
    with open(stats_path) as f:
        stats = json.load(f)
    assert "observation.images.wrist_depth" not in stats
    assert len(stats["observation.state"]["mean"]) == 6
    assert len(stats["action"]["mean"]) == 6


def test_prune_custom_features_and_slice_dof(tmp_path: Path):
    ds_dir = create_dummy_dataset(tmp_path)

    res = prune_dataset(
        dataset_path=ds_dir,
        slice_dof=4,
        slice_names=["j1", "j2", "j3", "j4"],
        drop_features=["custom_temp"],
    )

    assert res.sliced_dof == 4
    assert "custom_temp" in res.dropped_columns

    df = pd.read_parquet(ds_dir / "data" / "chunk-000" / "episode_0.parquet")
    assert "custom_temp" not in df.columns
    assert len(df["observation.state"].iloc[0]) == 4
    assert len(df["action"].iloc[0]) == 4

    info_path = ds_dir / "meta" / "info.json"
    with open(info_path) as f:
        info = json.load(f)
    assert "custom_temp" not in info["features"]
    assert info["features"]["observation.state"]["shape"] == [4]
    assert info["features"]["observation.state"]["names"] == ["j1", "j2", "j3", "j4"]


def test_prune_dry_run(tmp_path: Path):
    ds_dir = create_dummy_dataset(tmp_path)

    res = prune_dataset(
        dataset_path=ds_dir,
        drop_depth=True,
        drop_ee=True,
        dry_run=True,
    )

    assert res.modified_parquets == 1

    # Parquet file should remain untouched
    df = pd.read_parquet(ds_dir / "data" / "chunk-000" / "episode_0.parquet")
    assert "observation.images.wrist_depth" in df.columns
    assert len(df["observation.state"].iloc[0]) == 8
