"""Unit tests for ModularPhysicalWrapper and robot-specific subclasses."""

import numpy as np
import pytest
from clirobot.hardware.wrapper import (
    ModularPhysicalWrapper,
    ModularPhysicalWrapperConfig,
    So100PhysicalWrapper,
    So100PhysicalWrapperConfig,
    So101PhysicalWrapper,
    So101PhysicalWrapperConfig,
)
from clirobot.hardware.depth import decode_rgb_to_depth


class MockDepthCamera:
    def __init__(self, depth_arr: np.ndarray):
        self.latest_depth_frame = depth_arr
        self.height, self.width = depth_arr.shape[:2]


class DummyWrapper(ModularPhysicalWrapper):
    """Test subclass overriding hardware connect/super methods for offline unit testing."""

    def __init__(self, config: ModularPhysicalWrapperConfig, base_obs: dict, cameras: dict = None):
        # Bypass hardware SOFollower.__init__ to avoid connecting to real USB serial bus
        self.config = config
        self.cameras = cameras or {}
        self._base_obs = base_obs
        from clirobot.hardware.kinematics import ForwardKinematicsEngine
        from clirobot.hardware.depth import DepthFrameProcessor

        self.fk_engine = ForwardKinematicsEngine(
            robot_type=getattr(config, "robot_type", "so100"),
            urdf_name=getattr(config, "urdf_name", None),
            target_link=getattr(config, "target_link", "gripper"),
            scale=getattr(config, "scale", 50.0),
        )
        self.depth_processor = DepthFrameProcessor(
            max_depth_mm=getattr(config, "max_depth_mm", 3000.0),
            enable_vis=getattr(config, "enable_depth_vis", True),
        )

    def get_observation(self) -> dict:
        obs = self._base_obs.copy()

        if getattr(self.config, "enable_ee_pose", True):
            ee_pose = self.fk_engine.compute_ee_pose(obs)
            obs.update(ee_pose)

        if getattr(self.config, "enable_depth", True):
            depth_obs = self.depth_processor.populate_observations(
                cameras=self.cameras,
                target_cameras=getattr(self.config, "depth_cameras", None),
            )
            obs.update(depth_obs)

        return obs


def test_wrapper_configs():
    """Verify wrapper configuration dataclasses have expected default parameters."""
    m_cfg = ModularPhysicalWrapperConfig()
    assert m_cfg.enable_ee_pose is True
    assert m_cfg.enable_depth is True
    assert m_cfg.target_link == "gripper"

    so101_cfg = So101PhysicalWrapperConfig()
    assert so101_cfg.urdf_name == "so_arm101_description"
    assert so101_cfg.robot_type == "so101"
    assert so101_cfg.scale == 50.0

    so100_cfg = So100PhysicalWrapperConfig()
    assert so100_cfg.urdf_name == "so_arm100_description"
    assert so100_cfg.robot_type == "so100"


def test_observation_features_property():
    """Verify observation_features dynamically advertises EE pose and depth cameras."""
    cfg = ModularPhysicalWrapperConfig(
        enable_ee_pose=True,
        enable_depth=True,
        depth_cameras=["cam_high", "cam_wrist"],
    )
    wrapper = DummyWrapper(cfg, base_obs={})

    features = wrapper.observation_features
    # Kinematics features
    assert "ee_pos_x" in features
    assert "ee_pos_y" in features
    assert "ee_pos_z" in features
    assert "ee_quat_x" in features
    assert "ee_quat_y" in features
    assert "ee_quat_z" in features
    assert "ee_quat_w" in features

    # Multi-camera depth features
    assert "cam_high_depth" in features
    assert "cam_high_depth_vis" in features
    assert "cam_wrist_depth" in features
    assert "cam_wrist_depth_vis" in features


def test_get_observation_augmentation():
    """Verify get_observation successfully populates EE coords and 16-bit depth channels."""
    depth_image = np.ones((480, 640), dtype=np.uint16) * 1500  # 1.5 meters
    cameras = {
        "cam_high": MockDepthCamera(depth_image)
    }

    base_obs = {
        "shoulder_pan": 0.2,
        "shoulder_lift": -0.1,
        "elbow_flex": 0.3,
        "wrist_flex": 0.1,
        "wrist_roll": 0.0,
        "gripper": 0.0,
    }

    cfg = ModularPhysicalWrapperConfig(
        enable_ee_pose=True,
        enable_depth=True,
        depth_cameras=["cam_high"],
    )
    wrapper = DummyWrapper(cfg, base_obs=base_obs, cameras=cameras)

    full_obs = wrapper.get_observation()

    # Check EE coords
    assert "ee_pos_x" in full_obs
    assert "ee_pos_y" in full_obs
    assert "ee_pos_z" in full_obs
    assert "ee_quat_w" in full_obs
    assert isinstance(full_obs["ee_pos_x"], float)

    # Check Depth channels
    assert "cam_high_depth" in full_obs
    assert "cam_high_depth_vis" in full_obs
    assert full_obs["cam_high_depth"].shape == (480, 640, 3)

    # Check depth roundtrip
    decoded_depth = decode_rgb_to_depth(full_obs["cam_high_depth"])
    assert decoded_depth[0, 0] == 1500


def test_disabled_features():
    """Verify disabled toggles omit EE pose and depth channels."""
    cfg = ModularPhysicalWrapperConfig(
        enable_ee_pose=False,
        enable_depth=False,
    )
    wrapper = DummyWrapper(cfg, base_obs={"state": [0, 0, 0, 0, 0, 0]})
    full_obs = wrapper.get_observation()

    assert "ee_pos_x" not in full_obs
    assert "cam_high_depth" not in full_obs
