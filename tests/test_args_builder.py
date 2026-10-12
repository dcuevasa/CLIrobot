"""Tests for LeRobot CLI argument builder."""

from clirobot.config.schema import RobotProfile, ArmConfig, CameraConfig
from clirobot.integration.args_builder import LeRobotArgsBuilder


def test_build_teleoperate_args():
    profile = RobotProfile(
        name="test_profile",
        robot_type="so100",
        teleop_type="so100_leader",
        leader_arm=ArmConfig(port="/dev/ttyACM0"),
        follower_arm=ArmConfig(port="/dev/ttyACM1"),
        cameras={"laptop": CameraConfig(name="laptop", index_or_path="0")},
        default_fps=30,
    )

    args = LeRobotArgsBuilder.build_teleoperate_args(profile, display_cameras=True)
    assert "--robot.type=so100" in args
    assert "--teleop.type=so100_leader" in args
    assert "--teleop.port=/dev/ttyACM0" in args
    assert "--robot.port=/dev/ttyACM1" in args
    assert "--robot.cameras={laptop: 0}" in args
    assert "--fps=30" in args
    assert "--display_cameras=true" in args


def test_build_record_args():
    profile = RobotProfile(
        name="test_profile",
        robot_type="so100",
        teleop_type="so100_leader",
        leader_arm=ArmConfig(port="/dev/ttyACM0"),
        follower_arm=ArmConfig(port="/dev/ttyACM1"),
        dataset_repo_id="user/cool_dataset",
        default_fps=50,
    )

    args = LeRobotArgsBuilder.build_record_args(
        profile,
        num_episodes=5,
        episode_time_s=25.0,
        single_task="Pick red block",
        push_to_hub=True,
    )

    assert "--dataset.repo_id=user/cool_dataset" in args
    assert "--dataset.num_episodes=5" in args
    assert "--dataset.episode_time_s=25.0" in args
    assert "--dataset.single_task=Pick red block" in args
    assert "--dataset.push_to_hub=true" in args
    assert "--dataset.fps=50" in args


def test_build_calibrate_args():
    profile = RobotProfile(
        name="test_profile",
        robot_type="so100",
        follower_arm=ArmConfig(port="/dev/ttyACM1", arm_id="main"),
        leader_arm=ArmConfig(port="/dev/ttyACM0", arm_id="blue"),
    )

    follower_args = LeRobotArgsBuilder.build_calibrate_args(profile, arm="follower")
    assert "--robot.type=so100" in follower_args
    assert "--robot.port=/dev/ttyACM1" in follower_args
    assert "--robot.id=main" in follower_args

    leader_args = LeRobotArgsBuilder.build_calibrate_args(profile, arm="leader")
    assert "--robot.port=/dev/ttyACM0" in leader_args
    assert "--robot.id=blue" in leader_args


def test_build_train_args():
    args = LeRobotArgsBuilder.build_train_args(
        dataset_repo_id="lerobot/aloha_sim",
        policy_type="act",
        output_dir="outputs/train",
        batch_size=16,
        steps=50000,
        wandb_enable=True,
    )

    assert "--dataset.repo_id=lerobot/aloha_sim" in args
    assert "--policy.type=act" in args
    assert "--output_dir=outputs/train" in args
    assert "--batch_size=16" in args
    assert "--training.steps=50000" in args
    assert "--wandb.enable=true" in args


def test_build_teleoperate_args_with_ee_and_depth():
    profile = RobotProfile(
        name="test_kinematics_teleop",
        robot_type="modular_physical_wrapped",
        enable_ee_pose=True,
        enable_depth=True,
        urdf_name="so_arm101_description",
        target_link="gripper",
    )
    args = LeRobotArgsBuilder.build_teleoperate_args(
        profile,
        enable_ee_pose=True,
        enable_depth=True,
        urdf_name="custom_arm",
        target_link="end_effector_tip",
    )
    assert "--robot.enable_ee_pose=true" in args
    assert "--robot.enable_depth=true" in args
    assert "--robot.urdf_name=custom_arm" in args
    assert "--robot.target_link=end_effector_tip" in args


def test_build_record_args_with_ee_and_depth():
    profile = RobotProfile(
        name="test_kinematics_record",
        robot_type="so101_physical_wrapped",
        enable_ee_pose=True,
        enable_depth=True,
    )
    args = LeRobotArgsBuilder.build_record_args(
        profile,
        num_episodes=3,
        enable_ee_pose=True,
        enable_depth=True,
        urdf_name="so_arm101_description",
    )
    assert "--robot.enable_ee_pose=true" in args
    assert "--robot.enable_depth=true" in args
    assert "--robot.urdf_name=so_arm101_description" in args
