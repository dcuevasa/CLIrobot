"""Tests for terminal and OpenCV keyboard reader and event manager."""

from unittest.mock import patch, MagicMock
from clirobot.keyboard.terminal import TerminalKeyReader
from clirobot.keyboard.cv2_bridge import OpenCVKeyBridge
from clirobot.keyboard.listener import KeyboardManager


def test_terminal_key_parser():
    reader = TerminalKeyReader()

    # Simple characters
    assert reader._parse_key("q") == "q"
    assert reader._parse_key("R") == "r"
    assert reader._parse_key(" ") == "space"
    assert reader._parse_key("\r") == "enter"
    assert reader._parse_key("\n") == "enter"
    assert reader._parse_key("\x7f") == "backspace"
    assert reader._parse_key("\x03") == "ctrl_c"

    # Arrow keys and ANSI sequences
    with patch("clirobot.keyboard.terminal._read_char_posix", side_effect=["[", "A"]):
        assert reader._parse_key("\x1b") == "up"

    with patch("clirobot.keyboard.terminal._read_char_posix", side_effect=["[", "B"]):
        assert reader._parse_key("\x1b") == "down"

    with patch("clirobot.keyboard.terminal._read_char_posix", side_effect=["[", "C"]):
        assert reader._parse_key("\x1b") == "right"

    with patch("clirobot.keyboard.terminal._read_char_posix", side_effect=["[", "D"]):
        assert reader._parse_key("\x1b") == "left"

    # Standalone Esc
    with patch("clirobot.keyboard.terminal._read_char_posix", return_value=None):
        assert reader._parse_key("\x1b") == "esc"


def test_windows_key_mappings():
    from clirobot.keyboard.terminal import WINDOWS_SPECIAL_KEYS
    assert WINDOWS_SPECIAL_KEYS["H"] == "up"
    assert WINDOWS_SPECIAL_KEYS["P"] == "down"
    assert WINDOWS_SPECIAL_KEYS["K"] == "left"
    assert WINDOWS_SPECIAL_KEYS["M"] == "right"



def test_opencv_key_bridge():
    dispatched = []
    bridge = OpenCVKeyBridge(dispatch=lambda k: dispatched.append(k))

    assert bridge.process_key_code(ord("q")) == "q"
    assert bridge.process_key_code(ord(" ")) == "space"
    assert bridge.process_key_code(27) == "esc"
    assert bridge.process_key_code(81) == "left"
    assert bridge.process_key_code(83) == "right"
    assert bridge.process_key_code(-1) is None

    assert "q" in dispatched
    assert "space" in dispatched
    assert "esc" in dispatched
    assert "left" in dispatched
    assert "right" in dispatched


def test_keyboard_manager_state_flags():
    actions = []
    mgr = KeyboardManager(on_action=lambda k: actions.append(k))

    # Toggle pause
    mgr._handle_key_event("space")
    assert mgr.is_paused is True
    mgr._handle_key_event("space")
    assert mgr.is_paused is False

    # Trigger re-record
    mgr._handle_key_event("r")
    assert mgr.rerecord_requested is True

    # Trigger next episode
    mgr._handle_key_event("n")
    assert mgr.next_requested is True

    # Check get_events clears one-shot triggers
    events = mgr.get_events()
    assert events["rerecord_requested"] is True
    assert events["next_requested"] is True
    assert mgr.rerecord_requested is False
    assert mgr.next_requested is False

    # Trigger quit
    mgr._handle_key_event("q")
    assert mgr.stop_requested is True
