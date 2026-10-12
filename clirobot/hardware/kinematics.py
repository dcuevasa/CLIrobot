"""Forward kinematics engine and Cartesian coordinate tracking for robotic arms.

Computes 3D end-effector positions (ee_pos_x, ee_pos_y, ee_pos_z) and orientations
(ee_quat_x, ee_quat_y, ee_quat_z, ee_quat_w) from joint positions using URDF models
or analytical kinematics solvers for popular robot arms (SO-100, SO-101, Koch, Aloha).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

logger = logging.getLogger("clirobot.hardware.kinematics")

# Standard joint mappings for common LeRobot arms
DEFAULT_JOINT_MAPPINGS = {
    "so100": {
        "shoulder_pan": "1",
        "shoulder_lift": "2",
        "elbow_flex": "3",
        "wrist_flex": "4",
        "wrist_roll": "5",
        "gripper": "6",
    },
    "so101": {
        "shoulder_pan": "1",
        "shoulder_lift": "2",
        "elbow_flex": "3",
        "wrist_flex": "4",
        "wrist_roll": "5",
        "gripper": "6",
    },
    "koch": {
        "shoulder_pan": "1",
        "shoulder_lift": "2",
        "elbow_flex": "3",
        "wrist_flex": "4",
        "wrist_roll": "5",
        "gripper": "6",
    },
    "aloha": {
        "waist": "1",
        "shoulder": "2",
        "elbow": "3",
        "forearm_roll": "4",
        "wrist_angle": "5",
        "wrist_rotate": "6",
        "gripper": "7",
    },
}

# Standard URDF description names in robot_descriptions package
DEFAULT_URDF_NAMES = {
    "so100": "so_arm100_description",
    "so101": "so_arm101_description",
    "koch": "koch_description",
    "aloha": "aloha_description",
}


def matrix_to_quaternion(R: np.ndarray) -> np.ndarray:
    """Convert a 3x3 rotation matrix to quaternion [qx, qy, qz, qw]."""
    try:
        from scipy.spatial.transform import Rotation
        return Rotation.from_matrix(R).as_quat()
    except Exception:
        pass

    # Pure NumPy fallback (Shepperd's algorithm)
    R = np.asarray(R, dtype=np.float64)
    tr = R[0, 0] + R[1, 1] + R[2, 2]

    if tr > 0:
        S = np.sqrt(tr + 1.0) * 2
        qw = 0.25 * S
        qx = (R[2, 1] - R[1, 2]) / S
        qy = (R[0, 2] - R[2, 0]) / S
        qz = (R[1, 0] - R[0, 1]) / S
    elif (R[0, 0] > R[1, 1]) and (R[0, 0] > R[2, 2]):
        S = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        qw = (R[2, 1] - R[1, 2]) / S
        qx = 0.25 * S
        qy = (R[0, 1] + R[1, 0]) / S
        qz = (R[0, 2] + R[2, 0]) / S
    elif R[1, 1] > R[2, 2]:
        S = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        qw = (R[0, 2] - R[2, 0]) / S
        qx = (R[0, 1] + R[1, 0]) / S
        qy = 0.25 * S
        qz = (R[1, 2] + R[2, 1]) / S
    else:
        S = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        qw = (R[1, 0] - R[0, 1]) / S
        qx = (R[0, 2] + R[2, 0]) / S
        qy = (R[1, 2] + R[2, 1]) / S
        qz = 0.25 * S

    q = np.array([qx, qy, qz, qw], dtype=np.float64)
    norm = np.linalg.norm(q)
    return q / norm if norm > 0 else np.array([0.0, 0.0, 0.0, 1.0])


def matrix_to_euler_rpy(R: np.ndarray) -> np.ndarray:
    """Extract Roll-Pitch-Yaw angles (extrinsic XYZ) from a 3x3 rotation matrix."""
    sy = np.sqrt(R[0, 0] * R[0, 0] + R[1, 0] * R[1, 0])
    singular = sy < 1e-6

    if not singular:
        roll = np.arctan2(R[2, 1], R[2, 2])
        pitch = np.arctan2(-R[2, 0], sy)
        yaw = np.arctan2(R[1, 0], R[0, 0])
    else:
        roll = np.arctan2(-R[1, 2], R[1, 1])
        pitch = np.arctan2(-R[2, 0], sy)
        yaw = 0.0

    return np.array([roll, pitch, yaw], dtype=np.float64)


class AnalyticalKinematicsSolver:
    """Analytical Geometric Forward Kinematics for SO-100 / SO-101 and serial arms."""

    def __init__(self, arm_type: str = "so100"):
        self.arm_type = arm_type.lower()
        # Physical link lengths in meters (base, shoulder-to-elbow, elbow-to-wrist, wrist-to-gripper)
        if "so" in self.arm_type:
            self.d1 = 0.096   # Base to shoulder
            self.a2 = 0.116   # Shoulder to elbow
            self.a3 = 0.135   # Elbow to wrist
            self.d5 = 0.085   # Wrist to gripper tip
        else:
            self.d1 = 0.100
            self.a2 = 0.120
            self.a3 = 0.120
            self.d5 = 0.080

    def solve(self, q: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Compute end-effector position and rotation matrix from 5 joint angles (radians).

        q: [pan, lift, elbow, wrist_flex, wrist_roll]
        Returns:
            (pos_xyz, R_3x3)
        """
        # Ensure at least 5 joint angles
        q_padded = np.zeros(5, dtype=np.float64)
        q_padded[:min(len(q), 5)] = q[:5]

        theta1, theta2, theta3, theta4, theta5 = q_padded

        # Planar arm calculation in shoulder elevation plane
        # Shoulder-wrist angle sum:
        phi = theta2 + theta3 + theta4

        # Radial distance and Z in arm plane
        r = self.a2 * np.cos(theta2) + self.a3 * np.cos(theta2 + theta3) + self.d5 * np.cos(phi)
        z = self.d1 + self.a2 * np.sin(theta2) + self.a3 * np.sin(theta2 + theta3) + self.d5 * np.sin(phi)

        x = r * np.cos(theta1)
        y = r * np.sin(theta1)

        # Orientation matrix
        c1, s1 = np.cos(theta1), np.sin(theta1)
        cp, sp = np.cos(phi), np.sin(phi)
        c5, s5 = np.cos(theta5), np.sin(theta5)

        # Rotation matrix combining pan, pitch (phi), and roll (theta5)
        R_pitch = np.array([
            [cp, 0, sp],
            [0, 1, 0],
            [-sp, 0, cp]
        ])
        R_pan = np.array([
            [c1, -s1, 0],
            [s1, c1, 0],
            [0, 0, 1]
        ])
        R_roll = np.array([
            [1, 0, 0],
            [0, c5, -s5],
            [0, s5, c5]
        ])

        R = R_pan @ R_pitch @ R_roll
        return np.array([x, y, z], dtype=np.float64), R

    def solve_so100(self, q: Any) -> Tuple[np.ndarray, np.ndarray]:
        """Convenience solver for SO-100 arm geometry."""
        self.arm_type = "so100"
        self.d1, self.a2, self.a3, self.d5 = 0.096, 0.116, 0.135, 0.085
        return self.solve(np.asarray(q, dtype=np.float64))

    def solve_so101(self, q: Any) -> Tuple[np.ndarray, np.ndarray]:
        """Convenience solver for SO-101 arm geometry."""
        self.arm_type = "so101"
        self.d1, self.a2, self.a3, self.d5 = 0.096, 0.116, 0.135, 0.085
        return self.solve(np.asarray(q, dtype=np.float64))


class ForwardKinematicsEngine:
    """Modular Forward Kinematics Engine supporting URDF or analytical kinematics."""

    def __init__(
        self,
        robot_type: str = "so100",
        urdf_name: Optional[str] = None,
        urdf_path: Optional[Union[str, Path]] = None,
        target_link: str = "gripper",
        scale: float = 50.0,
        joint_mapping: Optional[Dict[str, str]] = None,
        include_euler: bool = False,
    ):
        self.robot_type = robot_type.lower()
        self.urdf_name = urdf_name or DEFAULT_URDF_NAMES.get(self.robot_type)
        self.urdf_path = Path(urdf_path) if urdf_path else None
        self.target_link = target_link
        self.scale = scale if scale != 0 else 1.0
        self.joint_mapping = joint_mapping or DEFAULT_JOINT_MAPPINGS.get(self.robot_type, DEFAULT_JOINT_MAPPINGS["so100"])
        self.include_euler = include_euler

        self.urdf = None
        self.urdf_joints = []
        self._init_urdf_loader()
        self.analytical_solver = AnalyticalKinematicsSolver(arm_type=self.robot_type)

    def _init_urdf_loader(self) -> None:
        """Attempt loading URDF if robot_descriptions/yourdfpy is available."""
        if self.urdf_path and self.urdf_path.exists():
            try:
                import yourdfpy
                self.urdf = yourdfpy.URDF.load(str(self.urdf_path))
                self.urdf_joints = [j.name for j in self.urdf.actuated_joints]
                logger.info(f"Loaded custom URDF from {self.urdf_path}")
                return
            except Exception as e:
                logger.debug(f"Failed loading custom URDF {self.urdf_path}: {e}")

        if self.urdf_name:
            try:
                from robot_descriptions.loaders.yourdfpy import load_robot_description
                self.urdf = load_robot_description(self.urdf_name)
                self.urdf_joints = [j.name for j in self.urdf.actuated_joints]
                logger.info(f"Loaded URDF description: {self.urdf_name}")
            except Exception as e:
                logger.debug(f"robot_descriptions load skipped for {self.urdf_name}: {e}")

    def _extract_joints(self, joint_values: Dict[str, Any]) -> Optional[np.ndarray]:
        """Extract at least 5 joint values (in radians) from observation dict."""
        if not joint_values or not isinstance(joint_values, dict):
            return None

        # 1. State array/tensor check
        for state_key in ["observation.state", "state", "observation.position", "position"]:
            if state_key in joint_values and joint_values[state_key] is not None:
                val = joint_values[state_key]
                if hasattr(val, "detach"):
                    arr = val.detach().cpu().numpy().flatten()
                else:
                    arr = np.asarray(val, dtype=np.float64).flatten()
                if len(arr) >= 5:
                    return arr[:5]

        # 2. Named joint keys check
        joint_names = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]
        found = False
        q_rad = []
        for name in joint_names:
            if f"{name}.pos" in joint_values and joint_values[f"{name}.pos"] is not None:
                q_rad.append(float(joint_values[f"{name}.pos"]) / self.scale)
                found = True
            elif name in joint_values and joint_values[name] is not None:
                q_rad.append(float(joint_values[name]) / self.scale)
                found = True
            else:
                q_rad.append(0.0)

        if found:
            return np.array(q_rad, dtype=np.float64)

        return None

    def compute_ee_pose(self, joint_values: Dict[str, Any]) -> Dict[str, float]:
        """Compute end-effector 3D position and orientation from observation joints.

        Args:
            joint_values: Dictionary of joint observations, e.g.
                {'shoulder_pan.pos': 10.0, 'shoulder_lift.pos': -5.0, ...} or
                {'state': [0.1, -0.2, 0.3, 0.4, 0.0, 0.0]}

        Returns:
            Dictionary containing ee_pos_x/y/z, ee_quat_x/y/z/w, and optional euler rpy.
        """
        q_rad = self._extract_joints(joint_values)
        if q_rad is None:
            return {}

        # Try URDF scene graph if loaded
        if self.urdf is not None:
            try:
                cfg = {}
                joint_names = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
                for i, (lerobot_name, urdf_num) in enumerate(self.joint_mapping.items()):
                    if urdf_num in self.urdf_joints:
                        if i < len(q_rad):
                            cfg[urdf_num] = float(q_rad[i])
                        else:
                            val = joint_values.get(f"{lerobot_name}.pos", joint_values.get(lerobot_name, 0.0))
                            cfg[urdf_num] = float(val) / self.scale

                self.urdf.update_cfg(cfg)
                ee_transform = self.urdf.scene.graph.get(self.target_link)[0]

                ee_pos = ee_transform[:3, 3]
                ee_rot = ee_transform[:3, :3]
                ee_quat = matrix_to_quaternion(ee_rot)

                pose_dict = {
                    "ee_pos_x": float(ee_pos[0]),
                    "ee_pos_y": float(ee_pos[1]),
                    "ee_pos_z": float(ee_pos[2]),
                    "ee_quat_x": float(ee_quat[0]),
                    "ee_quat_y": float(ee_quat[1]),
                    "ee_quat_z": float(ee_quat[2]),
                    "ee_quat_w": float(ee_quat[3]),
                }

                if self.include_euler:
                    rpy = matrix_to_euler_rpy(ee_rot)
                    pose_dict.update({
                        "ee_roll": float(rpy[0]),
                        "ee_pitch": float(rpy[1]),
                        "ee_yaw": float(rpy[2]),
                    })

                return pose_dict
            except Exception as e:
                logger.debug(f"URDF evaluation failed: {e}. Falling back to analytical FK.")

        # Analytical Kinematics Fallback
        pos, rot = self.analytical_solver.solve(q_rad)
        quat = matrix_to_quaternion(rot)

        pose_dict = {
            "ee_pos_x": float(pos[0]),
            "ee_pos_y": float(pos[1]),
            "ee_pos_z": float(pos[2]),
            "ee_quat_x": float(quat[0]),
            "ee_quat_y": float(quat[1]),
            "ee_quat_z": float(quat[2]),
            "ee_quat_w": float(quat[3]),
        }

        if self.include_euler:
            rpy = matrix_to_euler_rpy(rot)
            pose_dict.update({
                "ee_roll": float(rpy[0]),
                "ee_pitch": float(rpy[1]),
                "ee_yaw": float(rpy[2]),
            })

        return pose_dict
