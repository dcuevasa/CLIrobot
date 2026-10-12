"""Tests for serial port discovery and udev generation."""

from pathlib import Path
from unittest.mock import patch, MagicMock
from clirobot.hardware.ports import get_available_ports, SerialPortInfo
from clirobot.hardware.udev import generate_udev_rules
from clirobot.config.manager import ConfigManager


def test_get_available_ports_sorting_and_role_assignment():
    # Mock serial.tools.list_ports.comports
    p1 = MagicMock()
    p1.device = "/dev/ttyS0"
    p1.description = "Platform Serial"
    p1.hwid = ""
    p1.vid = None
    p1.pid = None
    p1.serial_number = None

    p2 = MagicMock()
    p2.device = "/dev/ttyACM0"
    p2.description = "Feetech Adapter"
    p2.hwid = "USB VID:PID=0403:6001"
    p2.vid = 0x0403
    p2.pid = 0x6001
    p2.serial_number = "FT12345"

    with patch("serial.tools.list_ports.comports", return_value=[p1, p2]):
        ports = get_available_ports(active_leader_port="/dev/ttyACM0", active_follower_port="")
        assert len(ports) == 1  # /dev/ttyS0 filtered out by default
        assert ports[0].device == "/dev/ttyACM0"
        assert ports[0].assigned_role == "Leader"
        assert ports[0].vid == 0x0403


def test_udev_rules_generation(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    mgr = ConfigManager(config_path=cfg_file)
    mgr.update_ports(leader_port="/dev/ttyACM0", follower_port="/dev/ttyACM1")

    p1 = MagicMock()
    p1.device = "/dev/ttyACM0"
    p1.vid = 0x1a86
    p1.pid = 0x7523
    p1.serial_number = "SER_LEADER_99"

    p2 = MagicMock()
    p2.device = "/dev/ttyACM1"
    p2.vid = 0x1a86
    p2.pid = 0x7523
    p2.serial_number = "SER_FOLLOWER_88"

    with patch("serial.tools.list_ports.comports", return_value=[p1, p2]):
        rules = generate_udev_rules(mgr)
        assert 'SYMLINK+="lerobot-leader"' in rules
        assert 'ATTRS{serial}=="SER_LEADER_99"' in rules
        assert 'SYMLINK+="lerobot-follower"' in rules
        assert 'ATTRS{serial}=="SER_FOLLOWER_88"' in rules
