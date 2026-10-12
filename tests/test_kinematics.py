"""Unit tests for robot kinematics, analytical forward kinematics, and pose tracking."""

import numpy as np
import pytest
import torch
from clirobot.hardware.kinematics import (
    AnalyticalKinematicsSolver,
    ForwardKinematicsEngine,
    matrix_to_quaternion,
)


def test_matrix_to_quaternion_identity():
    """Verify identity matrix converts to unit quaternion [0, 0, 0, 1]."""
    identity = np.eye(3, dtype=np.float64)
    q = matrix_to_quaternion(identity)
    assert len(q) == 4
    np.testing.assert_allclose(q, [0.0, 0.0, 0.0, 1.0], atol=1e-5)


def test_matrix_to_quaternion_rotation_z():
    """Verify 90-degree Z-axis rotation converts to [0, 0, sin(pi/4), cos(pi/4)]."""
    rot_z_90 = np.array([
        [0.0, -1.0, 0.0],
        [1.0,  0.0, 0.0],
        [0.0,  0.0, 1.0],
    ])
    q = matrix_to_quaternion(rot_z_90)
    expected_w = np.cos(np.pi / 4)
    expected_z = np.sin(np.pi / 4)
    np.testing.assert_allclose(q, [0.0, 0.0, expected_z, expected_w], atol=1e-4)


def test_analytical_kinematics_so100():
    """Verify analytical forward kinematics for SO-100 zero configuration and bent configuration."""
    solver = AnalyticalKinematicsSolver()

    # Zero joints
    pos0, rot0 = solver.solve_so100([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    assert len(pos0) == 3
    assert rot0.shape == (3, 3)
    # SO-100 at zero joints points forward and upward
    assert pos0[0] > 0.1  # X forward
    assert pos0[2] > 0.0  # Z above ground

    # Non-zero joints
    pos1, rot1 = solver.solve_so100([0.5, -0.3, 0.4, 0.2, 0.0, 0.0])
    assert len(pos1) == 3
    assert rot1.shape == (3, 3)
    # Check rotation matrix is orthogonal (R @ R.T == I)
    np.testing.assert_allclose(rot1 @ rot1.T, np.eye(3), atol=1e-5)


def test_analytical_kinematics_so101():
    """Verify analytical forward kinematics for SO-101."""
    solver = AnalyticalKinematicsSolver()
    pos, rot = solver.solve_so101([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    assert len(pos) == 3
    assert rot.shape == (3, 3)
    np.testing.assert_allclose(rot @ rot.T, np.eye(3), atol=1e-5)


def test_fk_engine_numpy_state():
    """Verify ForwardKinematicsEngine extracts joints from numpy array observation."""
    engine = ForwardKinematicsEngine(robot_type="so100", scale=50.0, include_euler=True)
    obs = {
        "observation.state": np.array([0.1, -0.2, 0.3, 0.4, 0.0, 0.0], dtype=np.float32)
    }

    ee_pose = engine.compute_ee_pose(obs)
    for key in ["ee_pos_x", "ee_pos_y", "ee_pos_z", "ee_quat_x", "ee_quat_y", "ee_quat_z", "ee_quat_w", "ee_roll", "ee_pitch", "ee_yaw"]:
        assert key in ee_pose
        assert isinstance(ee_pose[key], float)

    # Quaternion norm should be approximately 1.0
    quat_norm = np.sqrt(
        ee_pose["ee_quat_x"] ** 2
        + ee_pose["ee_quat_y"] ** 2
        + ee_pose["ee_quat_z"] ** 2
        + ee_pose["ee_quat_w"] ** 2
    )
    assert np.isclose(quat_norm, 1.0, atol=1e-4)


def test_fk_engine_torch_state():
    """Verify ForwardKinematicsEngine extracts joints from PyTorch tensor observation."""
    engine = ForwardKinematicsEngine(robot_type="so101")
    obs = {
        "state": torch.tensor([0.2, -0.1, 0.5, 0.1, 0.0, 0.0], dtype=torch.float32)
    }

    ee_pose = engine.compute_ee_pose(obs)
    assert "ee_pos_x" in ee_pose
    assert "ee_quat_w" in ee_pose
    assert isinstance(ee_pose["ee_pos_x"], float)


def test_fk_engine_named_joint_dict():
    """Verify ForwardKinematicsEngine extracts joints from dictionary of joint names."""
    engine = ForwardKinematicsEngine(robot_type="so100")
    obs = {
        "shoulder_pan": 0.15,
        "shoulder_lift": -0.25,
        "elbow_flex": 0.45,
        "wrist_flex": 0.1,
        "wrist_roll": 0.0,
        "gripper": 0.0,
    }

    ee_pose = engine.compute_ee_pose(obs)
    assert "ee_pos_x" in ee_pose
    assert "ee_pos_y" in ee_pose
    assert "ee_pos_z" in ee_pose


def test_fk_engine_missing_state():
    """Verify ForwardKinematicsEngine gracefully returns empty dict when no joint state found."""
    engine = ForwardKinematicsEngine(robot_type="so100")
    obs = {"unrelated_key": 42}
    ee_pose = engine.compute_ee_pose(obs)
    assert ee_pose == {}
