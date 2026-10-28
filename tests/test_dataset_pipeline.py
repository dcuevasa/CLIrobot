"""Unit tests for the Dataset Pipeline Engine."""

import json
from pathlib import Path
import pytest
from clirobot.config.manager import ConfigManager
from clirobot.dataset.pipeline import DatasetPipelineEngine, PipelineStep, load_pipeline_recipe


def test_pipeline_engine_list_transforms(tmp_path):
    cfg_file = tmp_path / "config.json"
    mgr = ConfigManager(config_path=cfg_file)
    engine = DatasetPipelineEngine(mgr)

    transforms = engine.list_available_transforms()
    assert "prune" in transforms
    assert "split" in transforms
    assert "vision-augment" in transforms
    assert "export-v3-language" in transforms


def test_pipeline_recipe_loading(tmp_path):
    recipe_dict = {
        "input": "lerobot/test-dataset",
        "meta": {"author": "Tester"},
        "steps": [
            {"transform": "split", "params": {"annotation_type": "subtask"}},
            {"transform": "prune", "params": {"drop_depth": True, "drop_ee": True}},
        ],
    }
    recipe_file = tmp_path / "recipe.json"
    recipe_file.write_text(json.dumps(recipe_dict))

    init_in, steps, meta = load_pipeline_recipe(recipe_file)
    assert init_in == "lerobot/test-dataset"
    assert len(steps) == 2
    assert steps[0].transform == "split"
    assert steps[1].transform == "prune"


def test_pipeline_dry_run_execution(tmp_path):
    cfg_file = tmp_path / "config.json"
    mgr = ConfigManager(config_path=cfg_file)
    engine = DatasetPipelineEngine(mgr)

    # Create dummy local dataset
    local_ds = tmp_path / "sample_ds"
    meta_dir = local_ds / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "info.json").write_text(json.dumps({"features": {}, "total_episodes": 1, "fps": 30}))
    data_dir = local_ds / "data" / "chunk-000"
    data_dir.mkdir(parents=True, exist_ok=True)

    steps = [
        PipelineStep(transform="prune", params={"drop_depth": True}),
        PipelineStep(transform="vision-augment", params={"cameras": ["cam_high"], "mode": "bbox"}),
    ]

    res = engine.run_pipeline(
        steps=steps,
        initial_input=str(local_ds),
        dry_run=True,
    )

    assert res.success is True
    assert len(res.step_results) == 2
    assert res.step_results[0].transform_id == "prune"
    assert res.step_results[1].transform_id == "vision-augment"


def test_pipeline_unknown_transform(tmp_path):
    cfg_file = tmp_path / "config.json"
    mgr = ConfigManager(config_path=cfg_file)
    engine = DatasetPipelineEngine(mgr)

    steps = [PipelineStep(transform="non_existent_transform_xyz")]
    res = engine.run_pipeline(steps=steps, initial_input="test/repo", dry_run=True)
    assert res.success is False
