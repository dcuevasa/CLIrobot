"""Unit tests for tool plugin adapters (Vision, Embodied, Visualizer)."""

from pathlib import Path
import pytest
from clirobot.config.manager import ConfigManager
from clirobot.integration.runner import CommandRunner
from clirobot.plugins.adapters.vision_detector import VisionDetectorPlugin
from clirobot.plugins.adapters.embodied_data import EmbodiedDataPlugin
from clirobot.plugins.adapters.dataset_visualizer import DatasetVisualizerPlugin
from clirobot.plugins.base import ExecutionPlan, PluginContext
from clirobot.ui.console import console


def test_vision_detector_middleware(tmp_path):
    cfg_file = tmp_path / "config.json"
    mgr = ConfigManager(config_path=cfg_file)
    ctx = PluginContext(mgr, CommandRunner(mgr), console)
    plugin = VisionDetectorPlugin()

    # Case 1: Disabled
    plan = ExecutionPlan(command_key="record", args=["--fps=30"])
    mutated = plugin.mutate_execution_plan(plan, ctx, runtime_options={"with_vision": False})
    assert "--detector.enabled=true" not in mutated.args

    # Case 2: Enabled via runtime options
    plan2 = ExecutionPlan(command_key="record", args=["--fps=30"])
    mutated2 = plugin.mutate_execution_plan(
        plan2,
        ctx,
        runtime_options={
            "with_vision": True,
            "vision_mode": "seg",
            "vision_cameras": ["cam_high"],
            "vision_targets": ["cup"],
        },
    )
    assert "--detector.enabled=true" in mutated2.args
    assert "--detector.mode=seg" in mutated2.args
    assert "--detector.cameras=cam_high" in mutated2.args
    assert "--detector.target_objects=cup" in mutated2.args
    assert mutated2.executable_override is not None
    assert "lerobot_vision_detector.cli.record" in mutated2.executable_override[1]


def test_vision_detector_transform_dry_run(tmp_path):
    cfg_file = tmp_path / "config.json"
    mgr = ConfigManager(config_path=cfg_file)
    ctx = PluginContext(mgr, CommandRunner(mgr), console)
    plugin = VisionDetectorPlugin()

    res = plugin.execute_transform(
        "vision-augment",
        ctx,
        input_repo="test/repo",
        output_repo="test/repo-detected",
        cameras=["cam_high"],
        mode="bbox",
        dry_run=True,
    )
    assert res.success is True
    assert res.metrics["dry_run"] is True


def test_embodied_data_middleware(tmp_path):
    cfg_file = tmp_path / "config.json"
    mgr = ConfigManager(config_path=cfg_file)
    ctx = PluginContext(mgr, CommandRunner(mgr), console)
    plugin = EmbodiedDataPlugin()

    # Set profile config
    mgr.set_plugin_config(
        "embodied-data",
        {"enable_ee_pose": True, "enable_depth": True, "reset_every_episode": True},
    )

    plan = ExecutionPlan(command_key="record", args=["--fps=30"])
    mutated = plugin.mutate_execution_plan(plan, ctx)
    assert "--robot.enable_ee_pose=true" in mutated.args
    assert "--robot.enable_depth=true" in mutated.args
    assert "--robot.reset_every_episode=true" in mutated.args


def test_embodied_data_import_env(tmp_path):
    cfg_file = tmp_path / "config.json"
    mgr = ConfigManager(config_path=cfg_file)

    script_content = """
FOLLOWER_PORT="/dev/ttyACM0"
LEADER_PORT="/dev/ttyACM1"
FOLLOWER_ID="follower_arm_test4"
LEADER_ID="leader_arm_test3"
ENABLE_EE_POSE="true"
ENABLE_DEPTH="true"
USE_CAM_HIGH="true"
USE_CAM_WRIST="true"
REPO_ID="test/so101-dataset"
"""
    sh_file = tmp_path / "set_variables.sh"
    sh_file.write_text(script_content)

    prof = mgr.import_env_script(sh_file, profile_name="test_imported")
    assert prof.name == "test_imported"
    assert prof.follower_arm.port == "/dev/ttyACM0"
    assert prof.leader_arm.port == "/dev/ttyACM1"
    assert prof.dataset_repo_id == "test/so101-dataset"
    assert "cam_high" in prof.cameras
    assert prof.cameras["cam_high"].camera_type == "intelrealsense"
    assert prof.cameras["cam_high"].use_depth is True
    assert "cam_wrist" in prof.cameras


def test_dataset_visualizer_status_and_dry_run(tmp_path):
    cfg_file = tmp_path / "config.json"
    mgr = ConfigManager(config_path=cfg_file)
    ctx = PluginContext(mgr, CommandRunner(mgr), console)
    plugin = DatasetVisualizerPlugin()

    stat = plugin.get_service_status(ctx)
    assert isinstance(stat.running, bool)

    res = plugin.execute_transform(
        "export-v3-language",
        ctx,
        input_repo="test/repo",
        dry_run=True,
    )
    assert res.success is True
    assert res.metrics["dry_run"] is True
