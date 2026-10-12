"""Configuration manager for persistent profiles and settings."""

import json
from pathlib import Path
from typing import Any
from clirobot.constants import CONFIG_DIR, CONFIG_FILE
from clirobot.config.schema import CLIrobotConfig, RobotProfile, ArmConfig, CameraConfig


class ConfigManager:
    """Handles loading, saving, and querying CLIrobot configuration and profiles."""

    def __init__(self, config_path: Path | None = None):
        import os
        env_path = os.environ.get("CLIROBOT_CONFIG_FILE")
        if config_path:
            self.config_path = config_path
        elif env_path:
            self.config_path = Path(env_path)
        else:
            self.config_path = CONFIG_FILE
        self.config = self._load_or_create()


    def _load_or_create(self) -> CLIrobotConfig:
        """Load existing config or initialize default configuration."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                config = CLIrobotConfig.from_dict(data)
                # Ensure at least one profile exists
                if not config.profiles:
                    config.profiles["default"] = self._create_default_profile("default")
                    config.active_profile = "default"
                elif config.active_profile not in config.profiles:
                    config.active_profile = next(iter(config.profiles.keys()))
                return config
            except Exception:
                # Corrupted or unreadable, fallback to default
                pass

        # Create fresh default configuration
        default_profile = self._create_default_profile("default")
        config = CLIrobotConfig(
            active_profile="default",
            profiles={"default": default_profile},
        )
        self.save(config)
        return config

    def _create_default_profile(self, name: str) -> RobotProfile:
        """Create a standard starter profile (SO-100 robot arm)."""
        return RobotProfile(
            name=name,
            robot_type="so100",
            robot_id="main",
            leader_arm=ArmConfig(port="", motor_type="feetech", baud_rate=1000000, arm_id="leader"),
            follower_arm=ArmConfig(port="", motor_type="feetech", baud_rate=1000000, arm_id="follower"),
            cameras={
                "laptop": CameraConfig(name="laptop", index_or_path="0", width=640, height=480, fps=30),
            },
            dataset_repo_id="lerobot/test",
            default_fps=30,
            teleop_type="so100_leader",
            notes="Default SO-100 configuration profile",
        )

    def save(self, config: CLIrobotConfig | None = None) -> None:
        """Persist configuration to disk."""
        if config is not None:
            self.config = config
        
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config.to_dict(), f, indent=2)

    def get_active_profile(self) -> RobotProfile:
        """Get the currently active profile."""
        if self.config.active_profile not in self.config.profiles:
            # Fallback if somehow missing
            if self.config.profiles:
                self.config.active_profile = next(iter(self.config.profiles.keys()))
            else:
                self.config.profiles["default"] = self._create_default_profile("default")
                self.config.active_profile = "default"
            self.save()
        return self.config.profiles[self.config.active_profile]

    def set_active_profile(self, name: str) -> bool:
        """Switch active profile by name."""
        if name in self.config.profiles:
            self.config.active_profile = name
            self.save()
            return True
        return False

    def list_profiles(self) -> list[str]:
        """List all available profile names."""
        return list(self.config.profiles.keys())

    def create_profile(
        self,
        name: str,
        robot_type: str = "so100",
        teleop_type: str | None = None,
        notes: str = "",
        clone_from: str | None = None,
    ) -> RobotProfile:
        """Create a new profile."""
        if clone_from and clone_from in self.config.profiles:
            source = self.config.profiles[clone_from]
            profile_data = source.to_dict()
            profile_data["name"] = name
            profile_data["notes"] = notes or f"Cloned from {clone_from}"
            profile = RobotProfile.from_dict(profile_data)
        else:
            profile = self._create_default_profile(name)
            profile.robot_type = robot_type
            profile.teleop_type = teleop_type or f"{robot_type}_leader"
            profile.notes = notes

        self.config.profiles[name] = profile
        self.save()
        return profile

    def delete_profile(self, name: str) -> bool:
        """Delete a profile (cannot delete last remaining profile)."""
        if name in self.config.profiles and len(self.config.profiles) > 1:
            del self.config.profiles[name]
            if self.config.active_profile == name:
                self.config.active_profile = next(iter(self.config.profiles.keys()))
            self.save()
            return True
        return False

    def update_ports(
        self,
        leader_port: str | None = None,
        follower_port: str | None = None,
        profile_name: str | None = None,
    ) -> RobotProfile:
        """Update follower/leader ports in the specified (or active) profile."""
        profile = self.config.profiles.get(profile_name) if profile_name else self.get_active_profile()
        if not profile:
            profile = self.get_active_profile()

        if leader_port is not None:
            if profile.leader_arm is None:
                profile.leader_arm = ArmConfig(arm_id="leader")
            profile.leader_arm.port = leader_port

        if follower_port is not None:
            if profile.follower_arm is None:
                profile.follower_arm = ArmConfig(arm_id="follower")
            profile.follower_arm.port = follower_port

        self.save()
        return profile

    def update_camera(
        self,
        name: str,
        index_or_path: str,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
        profile_name: str | None = None,
    ) -> RobotProfile:
        """Add or update a camera in the specified profile."""
        profile = self.config.profiles.get(profile_name) if profile_name else self.get_active_profile()
        if not profile:
            profile = self.get_active_profile()

        profile.cameras[name] = CameraConfig(
            name=name,
            index_or_path=str(index_or_path),
            width=width,
            height=height,
            fps=fps,
        )
        self.save()
        return profile

    def remove_camera(self, name: str, profile_name: str | None = None) -> bool:
        """Remove a camera from the profile."""
        profile = self.config.profiles.get(profile_name) if profile_name else self.get_active_profile()
        if profile and name in profile.cameras:
            del profile.cameras[name]
            self.save()
            return True
        return False
