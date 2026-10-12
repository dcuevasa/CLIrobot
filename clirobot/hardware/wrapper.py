"""Modular Robot Hardware Wrappers with Kinematics and Multi-Camera Depth Capture.

Augments any LeRobot robot with:
1. End-effector 3D Cartesian coordinates and orientation (FK / pose tracking)
2. Loss-tolerant 16-bit millimeter depth encoding and RGB colormapping for any depth camera
3. Generalization across multiple robot models (SO-100, SO-101, Koch, Aloha, custom arms)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Type

import numpy as np

from clirobot.hardware.kinematics import ForwardKinematicsEngine
from clirobot.hardware.depth import DepthFrameProcessor

logger = logging.getLogger("clirobot.hardware.wrapper")

# Gracefully import LeRobot base robot configs
try:
    from lerobot.robots.robot import Robot, RobotConfig
    from lerobot.robots.so_follower.so_follower import SOFollower, SOFollowerRobotConfig
    LEROBOT_ROBOTS_AVAILABLE = True
except ImportError:
    LEROBOT_ROBOTS_AVAILABLE = False

    class RobotConfig:  # type: ignore
        @classmethod
        def register_subclass(cls, name: str):
            def decorator(subclass):
                return subclass
            return decorator

    class SOFollowerRobotConfig(RobotConfig):  # type: ignore
        port: str = "/dev/ttyACM1"
        cameras: dict = field(default_factory=dict)
        id: str = "follower"
        type: str = "so100_follower"

    class Robot:  # type: ignore
        def __init__(self, config: Any):
            self.config = config
            self.cameras = {}

    class SOFollower(Robot):  # type: ignore
        pass


@dataclass
class RobotAugmentationConfig:
    """Configuration for kinematics and camera depth augmentation."""

    # Kinematics & End-Effector Tracking
    enable_ee_pose: bool = True
    robot_type: str = "so100"
    urdf_name: Optional[str] = None
    urdf_path: Optional[str] = None
    target_link: str = "gripper"
    scale: float = 50.0
    joint_mapping: Optional[Dict[str, str]] = None
    include_euler: bool = False

    # Multi-Camera Depth Processing
    enable_depth: bool = True
    enable_depth_vis: bool = True
    depth_cameras: Optional[List[str]] = None  # None = auto-detect all depth cameras
    max_depth_mm: float = 3000.0
    depth_colormap: str = "COLORMAP_JET"


# ==============================================================================
# Registered Robot Configurations
# ==============================================================================


@RobotConfig.register_subclass("modular_physical_wrapped")
@dataclass
class ModularPhysicalWrapperConfig(SOFollowerRobotConfig):
    """Modular robot wrapper config supporting forward kinematics and multi-camera depth."""

    port: str = "/dev/ttyACM1"
    enable_ee_pose: bool = True
    enable_depth: bool = True
    enable_depth_vis: bool = True
    robot_type: str = "so100"
    urdf_name: Optional[str] = None
    urdf_path: Optional[str] = None
    target_link: str = "gripper"
    scale: float = 50.0
    joint_mapping: Optional[Dict[str, str]] = None
    include_euler: bool = False
    depth_cameras: Optional[List[str]] = None
    max_depth_mm: float = 3000.0
    depth_colormap: str = "COLORMAP_JET"


@RobotConfig.register_subclass("so101_physical_wrapped")
@dataclass
class So101PhysicalWrapperConfig(SOFollowerRobotConfig):
    """SO-101 follower wrapper (compatible with lerobot_teleoperator_so101_ik)."""

    port: str = "/dev/ttyACM1"
    urdf_name: str = "so_arm101_description"
    target_link: str = "gripper"
    scale: float = 50.0
    enable_ee_pose: bool = True
    enable_depth: bool = True
    enable_depth_vis: bool = True
    depth_cameras: Optional[List[str]] = None
    max_depth_mm: float = 3000.0
    depth_colormap: str = "COLORMAP_JET"
    robot_type: str = "so101"
    urdf_path: Optional[str] = None
    joint_mapping: Optional[Dict[str, str]] = None
    include_euler: bool = False


@RobotConfig.register_subclass("so100_physical_wrapped")
@dataclass
class So100PhysicalWrapperConfig(SOFollowerRobotConfig):
    """SO-100 follower wrapper with kinematics and depth."""

    port: str = "/dev/ttyACM1"
    urdf_name: str = "so_arm100_description"
    target_link: str = "gripper"
    scale: float = 50.0
    enable_ee_pose: bool = True
    enable_depth: bool = True
    enable_depth_vis: bool = True
    depth_cameras: Optional[List[str]] = None
    max_depth_mm: float = 3000.0
    depth_colormap: str = "COLORMAP_JET"
    robot_type: str = "so100"
    urdf_path: Optional[str] = None
    joint_mapping: Optional[Dict[str, str]] = None
    include_euler: bool = False


# ==============================================================================
# Robot Implementations
# ==============================================================================


class ModularPhysicalWrapper(SOFollower):
    """Modular Physical Robot Wrapper.
    
    Augments base robot sensory observations with:
    1. Forward kinematics end-effector coordinates and quaternion orientation.
    2. Multi-camera 16-bit millimeter encoded depth and RGB visual colormapping.
    """

    config_class = ModularPhysicalWrapperConfig
    name = "modular_physical_wrapped"

    def __init__(self, config: ModularPhysicalWrapperConfig):
        super().__init__(config)
        self.config = config

        self.fk_engine = ForwardKinematicsEngine(
            robot_type=getattr(config, "robot_type", "so100"),
            urdf_name=getattr(config, "urdf_name", None),
            urdf_path=getattr(config, "urdf_path", None),
            target_link=getattr(config, "target_link", "gripper"),
            scale=getattr(config, "scale", 50.0),
            joint_mapping=getattr(config, "joint_mapping", None),
            include_euler=getattr(config, "include_euler", False),
        )

        self.depth_processor = DepthFrameProcessor(
            max_depth_mm=getattr(config, "max_depth_mm", 3000.0),
            enable_vis=getattr(config, "enable_depth_vis", True),
            colormap_name=getattr(config, "depth_colormap", "COLORMAP_JET"),
        )

    @property
    def observation_features(self) -> dict:
        try:
            obs = super().observation_features.copy()
        except Exception:
            obs = {}

        # 1. Forward Kinematics Features
        if getattr(self.config, "enable_ee_pose", True):
            obs.update({
                "ee_pos_x": float,
                "ee_pos_y": float,
                "ee_pos_z": float,
                "ee_quat_x": float,
                "ee_quat_y": float,
                "ee_quat_z": float,
                "ee_quat_w": float,
            })
            if getattr(self.config, "include_euler", False):
                obs.update({
                    "ee_roll": float,
                    "ee_pitch": float,
                    "ee_yaw": float,
                })

        # 2. Multi-Camera Depth Features
        if getattr(self.config, "enable_depth", True):
            target_cams = getattr(self.config, "depth_cameras", None)

            # Determine cameras to register
            cameras_to_check = (
                target_cams
                if target_cams
                else list(self.cameras.keys()) if hasattr(self, "cameras") and self.cameras else ["cam_high"]
            )

            for cam_name in cameras_to_check:
                # Resolve camera dimensions if configured
                cam_obj = getattr(self, "cameras", {}).get(cam_name)
                h = getattr(cam_obj, "height", 480)
                w = getattr(cam_obj, "width", 640)

                obs[f"{cam_name}_depth"] = (h, w, 3)
                if getattr(self.config, "enable_depth_vis", True):
                    obs[f"{cam_name}_depth_vis"] = (h, w, 3)

        return obs

    def get_observation(self) -> dict[str, Any]:
        obs = super().get_observation()

        # 1. Compute and Inject Forward Kinematics (EE Pose)
        if getattr(self.config, "enable_ee_pose", True):
            try:
                ee_pose = self.fk_engine.compute_ee_pose(obs)
                obs.update(ee_pose)
            except Exception as e:
                logger.debug(f"FK pose computation failed: {e}")

        # 2. Extract, Encode, and Inject Camera Depth Streams
        if getattr(self.config, "enable_depth", True):
            try:
                depth_obs = self.depth_processor.populate_observations(
                    cameras=getattr(self, "cameras", {}),
                    target_cameras=getattr(self.config, "depth_cameras", None),
                )
                obs.update(depth_obs)
            except Exception as e:
                logger.debug(f"Depth observation population failed: {e}")

        return obs


class So101PhysicalWrapper(ModularPhysicalWrapper):
    """SO-101 physical wrapper ensuring 100% drop-in compatibility with so101_physical_wrapped."""

    config_class = So101PhysicalWrapperConfig
    name = "so101_physical_wrapped"


class So100PhysicalWrapper(ModularPhysicalWrapper):
    """SO-100 physical wrapper with kinematics and multi-camera depth."""

    config_class = So100PhysicalWrapperConfig
    name = "so100_physical_wrapped"
