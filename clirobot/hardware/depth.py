"""Depth frame processing, 16-bit encoding/decoding, and colormap visualization.

Enables standard LeRobot video pipelines (MP4 / libsvtav1 / H.264) to capture and store
full 16-bit millimeter depth from Intel RealSense or depth-capable cameras alongside RGB streams.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import cv2


COLORMAP_MAP = {
    "COLORMAP_JET": cv2.COLORMAP_JET,
    "COLORMAP_TURBO": cv2.COLORMAP_TURBO if hasattr(cv2, "COLORMAP_TURBO") else cv2.COLORMAP_JET,
    "COLORMAP_VIRIDIS": cv2.COLORMAP_VIRIDIS if hasattr(cv2, "COLORMAP_VIRIDIS") else cv2.COLORMAP_JET,
    "COLORMAP_INFERNO": cv2.COLORMAP_INFERNO if hasattr(cv2, "COLORMAP_INFERNO") else cv2.COLORMAP_JET,
}


def encode_depth_to_rgb(raw_depth: np.ndarray) -> np.ndarray:
    """Encode a 16-bit depth map (in millimeters) into a 3-channel 8-bit RGB array.

    Enables storing loss-tolerant millimeter depth in standard 3-channel video containers:
    - Channel 0 (R): High 8 bits ((depth_mm >> 8) & 0xFF)
    - Channel 1 (G): Low 8 bits (depth_mm & 0xFF)
    - Channel 2 (B): Reserved (0)

    Args:
        raw_depth: 2D array (H, W) or (H, W, 1) of depth in millimeters (uint16 or float).

    Returns:
        3-channel uint8 array (H, W, 3).
    """
    if raw_depth.ndim == 3 and raw_depth.shape[-1] == 1:
        depth_2d = raw_depth[..., 0]
    elif raw_depth.ndim == 2:
        depth_2d = raw_depth
    else:
        depth_2d = np.squeeze(raw_depth)
        if depth_2d.ndim != 2:
            raise ValueError(f"Expected 2D depth frame, got shape {raw_depth.shape}")

    # Clip to valid 16-bit range (0 to 65535 mm = ~65.5 meters)
    depth_mm = np.clip(np.nan_to_num(depth_2d, nan=0.0, posinf=65535.0, neginf=0.0), 0, 65535).astype(np.uint16)

    h, w = depth_mm.shape
    encoded = np.zeros((h, w, 3), dtype=np.uint8)
    encoded[..., 0] = (depth_mm >> 8) & 0xFF  # High byte
    encoded[..., 1] = depth_mm & 0xFF         # Low byte
    encoded[..., 2] = 0

    return encoded


def decode_rgb_to_depth(encoded_rgb: np.ndarray) -> np.ndarray:
    """Decode a 3-channel encoded RGB depth frame back to 16-bit millimeter depth.

    Args:
        encoded_rgb: 3-channel uint8 array (H, W, 3).

    Returns:
        2D uint16 array (H, W) of depth in millimeters.
    """
    if encoded_rgb.ndim != 3 or encoded_rgb.shape[2] < 2:
        raise ValueError(f"Expected 3-channel uint8 array, got shape {encoded_rgb.shape}")

    high_byte = encoded_rgb[..., 0].astype(np.uint16)
    low_byte = encoded_rgb[..., 1].astype(np.uint16)

    depth_mm = (high_byte << 8) | low_byte
    return depth_mm


def colorize_depth(
    raw_depth: np.ndarray,
    max_depth_mm: float = 3000.0,
    colormap_type: int = cv2.COLORMAP_JET,
) -> np.ndarray:
    """Convert raw depth frame into a normalized, colormapped RGB visual image.

    Args:
        raw_depth: 2D array of depth in millimeters.
        max_depth_mm: Maximum depth range in millimeters (default: 3000 mm = 3 m).
        colormap_type: OpenCV colormap constant (e.g. cv2.COLORMAP_JET, cv2.COLORMAP_TURBO).

    Returns:
        3-channel uint8 RGB array (H, W, 3).
    """
    if raw_depth.ndim == 3 and raw_depth.shape[-1] == 1:
        depth_2d = raw_depth[..., 0].astype(np.float32)
    elif raw_depth.ndim == 2:
        depth_2d = raw_depth.astype(np.float32)
    else:
        depth_2d = np.squeeze(raw_depth).astype(np.float32)
        if depth_2d.ndim != 2:
            raise ValueError(f"Expected 2D depth frame, got shape {raw_depth.shape}")

    # Mark invalid/infinite/zero backgrounds
    bg_mask = (depth_2d <= 0.0) | np.isinf(depth_2d) | np.isnan(depth_2d)
    depth_vis = depth_2d.copy()
    depth_vis[bg_mask] = max_depth_mm

    # Normalize to [0, 1] then scale to [0, 255]
    depth_normalized = np.clip(depth_vis, 0, max_depth_mm) / max(1.0, max_depth_mm)
    depth_8bit = (depth_normalized * 255.0).astype(np.uint8)

    # Invert so closer objects are warm/bright
    depth_colormap_bgr = cv2.applyColorMap(255 - depth_8bit, colormap_type)
    return cv2.cvtColor(depth_colormap_bgr, cv2.COLOR_BGR2RGB)


class DepthFrameProcessor:
    """Universal multi-camera depth processor for robot hardware wrappers.
    
    Extracts, encodes, and visualizes depth channels from any connected camera
    providing depth information (e.g., Intel RealSense D435/D405/D415).
    """

    def __init__(
        self,
        max_depth_mm: float = 3000.0,
        enable_vis: bool = True,
        colormap_name: str = "COLORMAP_JET",
    ):
        self.max_depth_mm = max_depth_mm
        self.enable_vis = enable_vis
        self.colormap = COLORMAP_MAP.get(colormap_name, cv2.COLORMAP_JET)

    def process_frame(self, raw_depth: np.ndarray) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Process a single 2D depth frame into (encoded_depth, visual_depth)."""
        encoded = encode_depth_to_rgb(raw_depth)
        vis = colorize_depth(raw_depth, max_depth_mm=self.max_depth_mm, colormap_type=self.colormap) if self.enable_vis else None
        return encoded, vis

    def extract_from_camera(
        self,
        camera: Any,
        default_shape: Tuple[int, int] = (480, 640),
    ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Extract depth frame from a camera instance if available, or return zeros.

        Supports LeRobot RealSenseCamera attributes:
        - latest_depth_frame
        - depth_frame
        - read_depth()
        """
        raw_depth = None

        if hasattr(camera, "latest_depth_frame") and camera.latest_depth_frame is not None:
            raw_depth = camera.latest_depth_frame
        elif hasattr(camera, "depth_frame") and camera.depth_frame is not None:
            raw_depth = camera.depth_frame
        elif hasattr(camera, "read_depth") and callable(camera.read_depth):
            try:
                raw_depth = camera.read_depth()
            except Exception:
                pass

        if raw_depth is not None:
            return self.process_frame(raw_depth)

        # Fallback empty black frames
        h, w = getattr(camera, "height", default_shape[0]), getattr(camera, "width", default_shape[1])
        blank_encoded = np.zeros((h, w, 3), dtype=np.uint8)
        blank_vis = np.zeros((h, w, 3), dtype=np.uint8) if self.enable_vis else None
        return blank_encoded, blank_vis

    def populate_observations(
        self,
        cameras: Dict[str, Any],
        target_cameras: Optional[List[str]] = None,
        default_shape: Tuple[int, int] = (480, 640),
    ) -> Dict[str, np.ndarray]:
        """Process depth for all targeted cameras and return observation dictionary."""
        obs: Dict[str, np.ndarray] = {}

        for cam_name, cam_obj in cameras.items():
            if target_cameras is not None and cam_name not in target_cameras:
                continue

            # Check if camera has depth capabilities or was explicitly requested
            has_depth = (
                (target_cameras is not None and cam_name in target_cameras)
                or hasattr(cam_obj, "latest_depth_frame")
                or hasattr(cam_obj, "depth_frame")
                or hasattr(cam_obj, "read_depth")
                or "depth" in cam_name.lower()
                or getattr(cam_obj, "has_depth", False)
            )

            if has_depth:
                encoded, vis = self.extract_from_camera(cam_obj, default_shape=default_shape)
                obs[f"{cam_name}_depth"] = encoded
                if self.enable_vis and vis is not None:
                    obs[f"{cam_name}_depth_vis"] = vis

        return obs
