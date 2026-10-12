"""Configuration schema and dataclasses for CLIrobot."""

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ArmConfig:
    """Configuration for a robotic arm or leader device."""
    port: str = ""
    motor_type: str = "feetech"
    baud_rate: int = 1000000
    arm_id: str = "main"
    extra_args: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArmConfig":
        return cls(
            port=data.get("port", ""),
            motor_type=data.get("motor_type", "feetech"),
            baud_rate=data.get("baud_rate", 1000000),
            arm_id=data.get("arm_id", "main"),
            extra_args=data.get("extra_args", {}),
        )


@dataclass
class CameraConfig:
    """Configuration for a camera input."""
    name: str = "laptop"
    index_or_path: str = "0"
    width: int = 640
    height: int = 480
    fps: int = 30

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CameraConfig":
        return cls(
            name=data.get("name", "laptop"),
            index_or_path=str(data.get("index_or_path", "0")),
            width=int(data.get("width", 640)),
            height=int(data.get("height", 480)),
            fps=int(data.get("fps", 30)),
        )


@dataclass
class RobotProfile:
    """A saved profile combining robot type, arms, ports, cameras, and recording settings."""
    name: str = "default"
    robot_type: str = "so100"
    robot_id: str = "main"
    leader_arm: ArmConfig = field(default_factory=lambda: ArmConfig(arm_id="leader"))
    follower_arm: ArmConfig = field(default_factory=lambda: ArmConfig(arm_id="follower"))
    left_arm: ArmConfig | None = None
    right_arm: ArmConfig | None = None
    cameras: dict[str, CameraConfig] = field(default_factory=dict)
    dataset_repo_id: str = "lerobot/test"
    default_fps: int = 30
    teleop_type: str = "so100_leader"
    calibration_dir: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["leader_arm"] = self.leader_arm.to_dict() if self.leader_arm else None
        data["follower_arm"] = self.follower_arm.to_dict() if self.follower_arm else None
        data["left_arm"] = self.left_arm.to_dict() if self.left_arm else None
        data["right_arm"] = self.right_arm.to_dict() if self.right_arm else None
        data["cameras"] = {k: v.to_dict() for k, v in self.cameras.items()}
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RobotProfile":
        leader_raw = data.get("leader_arm")
        follower_raw = data.get("follower_arm")
        left_raw = data.get("left_arm")
        right_raw = data.get("right_arm")
        cameras_raw = data.get("cameras", {})

        return cls(
            name=data.get("name", "default"),
            robot_type=data.get("robot_type", "so100"),
            robot_id=data.get("robot_id", "main"),
            leader_arm=ArmConfig.from_dict(leader_raw) if leader_raw else ArmConfig(arm_id="leader"),
            follower_arm=ArmConfig.from_dict(follower_raw) if follower_raw else ArmConfig(arm_id="follower"),
            left_arm=ArmConfig.from_dict(left_raw) if left_raw else None,
            right_arm=ArmConfig.from_dict(right_raw) if right_raw else None,
            cameras={k: CameraConfig.from_dict(v) for k, v in cameras_raw.items()},
            dataset_repo_id=data.get("dataset_repo_id", "lerobot/test"),
            default_fps=int(data.get("default_fps", 30)),
            teleop_type=data.get("teleop_type", "so100_leader"),
            calibration_dir=data.get("calibration_dir", ""),
            notes=data.get("notes", ""),
        )


@dataclass
class CLIrobotConfig:
    """Global configuration holding all profiles and execution settings."""
    active_profile: str = "default"
    profiles: dict[str, RobotProfile] = field(default_factory=dict)
    lerobot_path: str = ""
    auto_save_ports: bool = True
    default_backend: str = "auto"  # auto, path, venv, conda

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_profile": self.active_profile,
            "profiles": {k: v.to_dict() for k, v in self.profiles.items()},
            "lerobot_path": self.lerobot_path,
            "auto_save_ports": self.auto_save_ports,
            "default_backend": self.default_backend,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CLIrobotConfig":
        profiles_raw = data.get("profiles", {})
        profiles = {k: RobotProfile.from_dict(v) for k, v in profiles_raw.items()}
        return cls(
            active_profile=data.get("active_profile", "default"),
            profiles=profiles,
            lerobot_path=data.get("lerobot_path", ""),
            auto_save_ports=data.get("auto_save_ports", True),
            default_backend=data.get("default_backend", "auto"),
        )
