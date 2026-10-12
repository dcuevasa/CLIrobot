"""Unit tests for camera depth frame processing, 16-bit millimeter encoding, and colormapping."""

import numpy as np
import pytest
from clirobot.hardware.depth import (
    DepthFrameProcessor,
    colorize_depth,
    decode_rgb_to_depth,
    encode_depth_to_rgb,
)


def test_depth_encode_decode_roundtrip():
    """Verify lossless 16-bit millimeter encoding into uint8 RGB and decoding back."""
    # Test key millimeter values: 0, 1, 255, 256, 1234, 3000, 65535
    test_values = np.array([
        [0, 1, 255],
        [256, 512, 1000],
        [3210, 15000, 65535],
    ], dtype=np.uint16)

    encoded = encode_depth_to_rgb(test_values)
    assert encoded.shape == (3, 3, 3)
    assert encoded.dtype == np.uint8

    # High byte in R, low byte in G, 0 in B
    assert encoded[0, 0, 0] == 0 and encoded[0, 0, 1] == 0
    assert encoded[0, 1, 0] == 0 and encoded[0, 1, 1] == 1
    assert encoded[0, 2, 0] == 0 and encoded[0, 2, 1] == 255
    assert encoded[1, 0, 0] == 1 and encoded[1, 0, 1] == 0
    assert encoded[2, 2, 0] == 255 and encoded[2, 2, 1] == 255

    decoded = decode_rgb_to_depth(encoded)
    assert decoded.shape == (3, 3)
    assert decoded.dtype == np.uint16
    np.testing.assert_array_equal(decoded, test_values)


def test_depth_encode_float_input():
    """Verify float millimeter depth arrays are safely cast and encoded."""
    raw_depth = np.array([[100.4, 2500.9]], dtype=np.float32)
    encoded = encode_depth_to_rgb(raw_depth)
    decoded = decode_rgb_to_depth(encoded)

    assert decoded[0, 0] == 100
    assert decoded[0, 1] == 2500


def test_depth_colorize():
    """Verify depth visualization colormap normalization and output dimensions."""
    depth_map = np.linspace(0, 3000, 100, dtype=np.uint16).reshape((10, 10))
    vis = colorize_depth(depth_map, max_depth_mm=3000.0)

    assert vis.shape == (10, 10, 3)
    assert vis.dtype == np.uint8
    # Min depth should be mapped to near 0, max depth to near 255
    assert vis.min() >= 0
    assert vis.max() <= 255


class MockCameraWithDepth:
    def __init__(self, depth_arr: np.ndarray, width: int = 640, height: int = 480):
        self._depth = depth_arr
        self.width = width
        self.height = height

    def read_depth(self) -> np.ndarray:
        return self._depth


class MockCameraWithProperty:
    def __init__(self, depth_arr: np.ndarray):
        self.latest_depth_frame = depth_arr
        self.width = depth_arr.shape[1]
        self.height = depth_arr.shape[0]


class MockStandardRgbCamera:
    def __init__(self):
        self.width = 640
        self.height = 480


def test_depth_frame_processor_multi_camera():
    """Verify processor discovers depth across multiple cameras and injects observations."""
    processor = DepthFrameProcessor(max_depth_mm=3000.0, enable_vis=True)

    depth1 = np.ones((480, 640), dtype=np.uint16) * 1200
    depth2 = np.ones((240, 320), dtype=np.uint16) * 800

    cameras = {
        "cam_overhead": MockCameraWithDepth(depth1, 640, 480),
        "cam_wrist": MockCameraWithProperty(depth2),
        "cam_rgb_only": MockStandardRgbCamera(),
    }

    obs = processor.populate_observations(cameras)

    assert "cam_overhead_depth" in obs
    assert "cam_overhead_depth_vis" in obs
    assert obs["cam_overhead_depth"].shape == (480, 640, 3)
    assert obs["cam_overhead_depth_vis"].shape == (480, 640, 3)

    # Check decoded value
    decoded1 = decode_rgb_to_depth(obs["cam_overhead_depth"])
    assert decoded1[0, 0] == 1200

    assert "cam_wrist_depth" in obs
    assert "cam_wrist_depth_vis" in obs
    assert obs["cam_wrist_depth"].shape == (240, 320, 3)

    # Standard RGB camera without depth should not produce depth keys
    assert "cam_rgb_only_depth" not in obs


def test_depth_frame_processor_filtered_cameras():
    """Verify processor filters to specified target cameras."""
    processor = DepthFrameProcessor(max_depth_mm=3000.0, enable_vis=False)

    depth1 = np.ones((100, 100), dtype=np.uint16) * 500
    depth2 = np.ones((100, 100), dtype=np.uint16) * 1500

    cameras = {
        "cam_high": MockCameraWithDepth(depth1),
        "cam_low": MockCameraWithDepth(depth2),
    }

    obs = processor.populate_observations(cameras, target_cameras=["cam_high"])
    assert "cam_high_depth" in obs
    assert "cam_high_depth_vis" not in obs  # enable_vis=False
    assert "cam_low_depth" not in obs
