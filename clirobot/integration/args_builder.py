"""Constructs and merges command-line arguments for LeRobot commands from active profiles."""

from typing import Any
from clirobot.config.schema import RobotProfile


class LeRobotArgsBuilder:
    """Intelligently builds arguments for LeRobot scripts using active profile settings and CLI overrides."""

    @staticmethod
    def format_cameras_arg(cameras: dict[str, Any]) -> str:
        """Format cameras dict for LeRobot CLI.
        
        Example format: "{laptop: 0, wrist: 1}" or typed dictionary for RealSense/custom.
        """
        if not cameras:
            return "{}"
        items = []
        for name, cam in cameras.items():
            cam_type = getattr(cam, "camera_type", "opencv")
            if cam_type == "intelrealsense":
                serial = getattr(cam, "serial_number_or_name", None) or getattr(cam, "index_or_path", "0")
                use_d = str(getattr(cam, "use_depth", False)).lower()
                w = getattr(cam, "width", 640)
                h = getattr(cam, "height", 480)
                fps = getattr(cam, "fps", 30)
                items.append(
                    f'"{name}": {{"type": "intelrealsense", "serial_number_or_name": "{serial}", '
                    f'"width": {w}, "height": {h}, "fps": {fps}, "use_depth": {use_d}}}'
                )
            else:
                idx = getattr(cam, "index_or_path", cam)
                items.append(f"{name}: {idx}")
        return "{" + ", ".join(items) + "}"

    @classmethod
    def build_teleoperate_args(
        cls,
        profile: RobotProfile,
        fps: int | None = None,
        display_cameras: bool = True,
        extra_args: list[str] | None = None,
    ) -> list[str]:
        """Build argument list for lerobot-teleoperate."""
        args: list[str] = []

        if profile.robot_type:
            args.append(f"--robot.type={profile.robot_type}")

        if profile.teleop_type:
            args.append(f"--teleop.type={profile.teleop_type}")

        # Set leader port if configured
        if profile.leader_arm and profile.leader_arm.port:
            args.append(f"--teleop.port={profile.leader_arm.port}")

        # Set follower port if configured
        if profile.follower_arm and profile.follower_arm.port:
            args.append(f"--robot.port={profile.follower_arm.port}")

        if profile.cameras:
            cams_str = cls.format_cameras_arg(profile.cameras)
            args.append(f"--robot.cameras={cams_str}")

        target_fps = fps or profile.default_fps
        if target_fps:
            args.append(f"--fps={target_fps}")

        if display_cameras:
            args.append("--display_cameras=true")

        if extra_args:
            args.extend(extra_args)

        return args

    @classmethod
    def build_record_args(
        cls,
        profile: RobotProfile,
        repo_id: str | None = None,
        num_episodes: int = 10,
        episode_time_s: float = 30.0,
        warmup_time_s: float = 3.0,
        reset_time_s: float = 5.0,
        single_task: str | None = None,
        fps: int | None = None,
        push_to_hub: bool = False,
        display_data: bool = False,
        play_sounds: bool = False,
        streaming_encoding: bool = False,
        reset_every_episode: bool = False,
        resume: bool = False,
        batch_encoding_size: int | None = None,
        private: bool = False,
        tags: list[str] | None = None,
        extra_args: list[str] | None = None,
    ) -> list[str]:
        """Build argument list for lerobot-record with smart profile integration and recording QoL flags."""
        args: list[str] = []

        if profile.robot_type:
            args.append(f"--robot.type={profile.robot_type}")

        if profile.teleop_type:
            args.append(f"--teleop.type={profile.teleop_type}")

        if profile.leader_arm and profile.leader_arm.port:
            args.append(f"--teleop.port={profile.leader_arm.port}")

        if profile.follower_arm and profile.follower_arm.port:
            args.append(f"--robot.port={profile.follower_arm.port}")

        if profile.cameras:
            cams_str = cls.format_cameras_arg(profile.cameras)
            args.append(f"--robot.cameras={cams_str}")

        target_repo = repo_id or profile.dataset_repo_id
        if target_repo:
            args.append(f"--dataset.repo_id={target_repo}")

        target_fps = fps or profile.default_fps
        if target_fps:
            args.append(f"--dataset.fps={target_fps}")

        args.append(f"--dataset.num_episodes={num_episodes}")
        args.append(f"--dataset.episode_time_s={episode_time_s}")
        args.append(f"--dataset.warmup_time_s={warmup_time_s}")
        args.append(f"--dataset.reset_time_s={reset_time_s}")

        if single_task:
            args.append(f"--dataset.single_task={single_task}")

        if push_to_hub:
            args.append("--dataset.push_to_hub=true")

        if private:
            args.append("--dataset.private=true")

        if tags:
            tags_str = "[" + ", ".join(f'"{t}"' for t in tags) + "]"
            args.append(f"--dataset.tags={tags_str}")

        # Recording QoL features
        if display_data:
            args.append("--display_data=true")

        if play_sounds:
            args.append("--play_sounds=true")

        if streaming_encoding:
            args.append("--dataset.streaming_encoding=true")

        if reset_every_episode:
            args.append("--robot.reset_every_episode=true")

        if resume:
            args.append("--resume=true")

        if batch_encoding_size is not None:
            args.append(f"--dataset.video_encoding_batch_size={batch_encoding_size}")

        if extra_args:
            args.extend(extra_args)

        return args

    @classmethod
    def build_replay_args(
        cls,
        profile: RobotProfile,
        repo_id: str | None = None,
        episode: int = 0,
        fps: int | None = None,
        extra_args: list[str] | None = None,
    ) -> list[str]:
        """Build argument list for lerobot-replay."""
        args: list[str] = []

        if profile.robot_type:
            args.append(f"--robot.type={profile.robot_type}")

        if profile.follower_arm and profile.follower_arm.port:
            args.append(f"--robot.port={profile.follower_arm.port}")

        target_repo = repo_id or profile.dataset_repo_id
        if target_repo:
            args.append(f"--dataset.repo_id={target_repo}")

        args.append(f"--dataset.episode={episode}")

        target_fps = fps or profile.default_fps
        if target_fps:
            args.append(f"--fps={target_fps}")

        if extra_args:
            args.extend(extra_args)

        return args

    @classmethod
    def build_calibrate_args(
        cls,
        profile: RobotProfile,
        arm: str = "follower",
        extra_args: list[str] | None = None,
    ) -> list[str]:
        """Build argument list for lerobot-calibrate."""
        args: list[str] = []

        if arm == "leader":
            robot_type = profile.teleop_type or f"{profile.robot_type}_leader"
            port = profile.leader_arm.port if profile.leader_arm else ""
            arm_id = profile.leader_arm.arm_id if profile.leader_arm else "leader"
        else:
            robot_type = profile.robot_type
            port = profile.follower_arm.port if profile.follower_arm else ""
            arm_id = profile.follower_arm.arm_id if profile.follower_arm else "follower"

        if robot_type:
            args.append(f"--robot.type={robot_type}")

        if port:
            args.append(f"--robot.port={port}")

        if arm_id:
            args.append(f"--robot.id={arm_id}")

        if profile.cameras:
            cams_str = cls.format_cameras_arg(profile.cameras)
            args.append(f"--robot.cameras={cams_str}")

        if extra_args:
            args.extend(extra_args)

        return args

    @classmethod
    def build_train_args(
        cls,
        dataset_repo_id: str,
        policy_type: str = "act",
        output_dir: str | None = None,
        batch_size: int = 8,
        steps: int = 100000,
        device: str = "cuda",
        wandb_enable: bool = False,
        extra_args: list[str] | None = None,
    ) -> list[str]:
        """Build argument list for lerobot-train."""
        args: list[str] = [
            f"--dataset.repo_id={dataset_repo_id}",
            f"--policy.type={policy_type}",
            f"--batch_size={batch_size}",
            f"--training.steps={steps}",
            f"--device={device}",
        ]

        if output_dir:
            args.append(f"--output_dir={output_dir}")

        if wandb_enable:
            args.append("--wandb.enable=true")

        if extra_args:
            args.extend(extra_args)

        return args
