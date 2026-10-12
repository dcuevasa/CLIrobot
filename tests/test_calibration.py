"""Tests for calibration manager, visual inspector, backups, and diff."""

import json
from pathlib import Path
from clirobot.calibration.manager import CalibrationManager
from clirobot.calibration.inspector import inspect_calibration, diff_calibrations


SAMPLE_CALIBRATION_A = {
    "shoulder_pan": {
        "homing_offset": 100,
        "start_pos": 0,
        "end_pos": 4096,
        "calibrated": True,
        "drive_mode": 0,
    },
    "shoulder_lift": {
        "homing_offset": -50,
        "start_pos": 500,
        "end_pos": 3500,
        "calibrated": True,
        "drive_mode": 1,
    },
}

SAMPLE_CALIBRATION_B = {
    "shoulder_pan": {
        "homing_offset": 120,
        "start_pos": 10,
        "end_pos": 4100,
        "calibrated": True,
        "drive_mode": 0,
    },
    "shoulder_lift": {
        "homing_offset": -50,
        "start_pos": 500,
        "end_pos": 3600,
        "calibrated": True,
        "drive_mode": 1,
    },
}


def test_calibration_manager_discovery_and_backups(tmp_path: Path):
    cache_dir = tmp_path / "cache" / "calibration"
    robot_dir = cache_dir / "so100"
    robot_dir.mkdir(parents=True, exist_ok=True)

    file_a = robot_dir / "main.json"
    with open(file_a, "w") as f:
        json.dump(SAMPLE_CALIBRATION_A, f)

    mgr = CalibrationManager(custom_cache_dir=cache_dir, include_global_cache=False)
    items = mgr.list_calibrations()
    assert len(items) == 1
    assert items[0].robot_type == "so100"
    assert items[0].robot_id == "main"

    # Test inspection doesn't throw
    inspect_calibration(items[0])

    # Test backup
    backed_up = mgr.backup()
    assert len(backed_up) == 1
    assert backed_up[0].exists()

    # Test export
    export_path = tmp_path / "export.json"
    mgr.export_calibration("so100/main", export_path)
    assert export_path.exists()

    # Test import
    imported = mgr.import_calibration(export_path, robot_type="so100", robot_id="imported_arm")
    assert imported.exists()

    # Verify both exist now
    refreshed = mgr.list_calibrations()
    assert len(refreshed) == 2


def test_calibration_diff(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    fa = cache_dir / "a.json"
    fb = cache_dir / "b.json"

    with open(fa, "w") as f:
        json.dump(SAMPLE_CALIBRATION_A, f)
    with open(fb, "w") as f:
        json.dump(SAMPLE_CALIBRATION_B, f)

    mgr = CalibrationManager(custom_cache_dir=cache_dir, include_global_cache=False)

    info_a = mgr.get_calibration("a.json")
    info_b = mgr.get_calibration("b.json")

    assert info_a is not None
    assert info_b is not None

    # Test diff runs smoothly
    diff_calibrations(info_a, info_b)
