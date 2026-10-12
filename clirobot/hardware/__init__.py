"""Hardware interfaces, port management, camera setup, kinematics, and robot wrappers."""

from clirobot.hardware.ports import SerialPortInfo, get_available_ports
from clirobot.hardware.cameras import CameraInfo, scan_cameras
from clirobot.hardware.udev import generate_udev_rules
from clirobot.hardware.kinematics import ForwardKinematicsEngine, AnalyticalKinematicsSolver, matrix_to_quaternion
from clirobot.hardware.depth import (
    DepthFrameProcessor,
    encode_depth_to_rgb,
    decode_rgb_to_depth,
    colorize_depth,
)
from clirobot.hardware.wrapper import (
    ModularPhysicalWrapper,
    ModularPhysicalWrapperConfig,
    So101PhysicalWrapper,
    So101PhysicalWrapperConfig,
    So100PhysicalWrapper,
    So100PhysicalWrapperConfig,
)

__all__ = [
    "SerialPortInfo",
    "get_available_ports",
    "CameraInfo",
    "scan_cameras",
    "generate_udev_rules",
    "ForwardKinematicsEngine",
    "AnalyticalKinematicsSolver",
    "matrix_to_quaternion",
    "DepthFrameProcessor",
    "encode_depth_to_rgb",
    "decode_rgb_to_depth",
    "colorize_depth",
    "ModularPhysicalWrapper",
    "ModularPhysicalWrapperConfig",
    "So101PhysicalWrapper",
    "So101PhysicalWrapperConfig",
    "So100PhysicalWrapper",
    "So100PhysicalWrapperConfig",
]
