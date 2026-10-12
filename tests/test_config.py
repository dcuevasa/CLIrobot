"""Tests for configuration and profile management."""

import pytest
import json
from pathlib import Path
from clirobot.config.schema import ArmConfig, CameraConfig, RobotProfile, CLIrobotConfig
from clirobot.config.manager import ConfigManager


def test_arm_config_serialization():
    arm = ArmConfig(port="/dev/ttyACM0", motor_type="feetech", baud_rate=1000000, arm_id="leader")
    data = arm.to_dict()
    assert data["port"] == "/dev/ttyACM0"
    assert data["motor_type"] == "feetech"

    rebuilt = ArmConfig.from_dict(data)
    assert rebuilt.port == "/dev/ttyACM0"
    assert rebuilt.baud_rate == 1000000


def test_camera_config_serialization():
    cam = CameraConfig(name="wrist", index_or_path="1", width=1280, height=720, fps=60)
    data = cam.to_dict()
    assert data["name"] == "wrist"
    assert data["index_or_path"] == "1"

    rebuilt = CameraConfig.from_dict(data)
    assert rebuilt.width == 1280
    assert rebuilt.fps == 60


def test_robot_profile_lifecycle(tmp_path: Path):
    config_file = tmp_path / "config.json"
    mgr = ConfigManager(config_path=config_file)

    # Verify default profile initialized
    active = mgr.get_active_profile()
    assert active.name == "default"
    assert active.robot_type == "so100"

    # Create new profile
    p2 = mgr.create_profile("koch-desk", robot_type="koch", notes="Koch arm setup")
    assert "koch-desk" in mgr.list_profiles()
    assert p2.robot_type == "koch"

    # Switch profile
    assert mgr.set_active_profile("koch-desk")
    assert mgr.get_active_profile().name == "koch-desk"

    # Update ports
    mgr.update_ports(leader_port="/dev/ttyACM0", follower_port="/dev/ttyACM1")
    updated = mgr.get_active_profile()
    assert updated.leader_arm.port == "/dev/ttyACM0"
    assert updated.follower_arm.port == "/dev/ttyACM1"

    # Update camera
    mgr.update_camera("overhead", "2", width=1920, height=1080)
    assert "overhead" in mgr.get_active_profile().cameras
    assert mgr.get_active_profile().cameras["overhead"].width == 1920

    # Remove camera
    assert mgr.remove_camera("overhead")
    assert "overhead" not in mgr.get_active_profile().cameras

    # Persistence verification: reload from disk
    reloaded_mgr = ConfigManager(config_path=config_file)
    assert reloaded_mgr.config.active_profile == "koch-desk"
    assert reloaded_mgr.get_active_profile().leader_arm.port == "/dev/ttyACM0"
