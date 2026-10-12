"""Tests for TUI menu navigation and interactive components."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from clirobot.tui.menu import MenuItem, run_menu, _fallback_number_selection
from clirobot.tui.app import TUIApp
from clirobot.config.manager import ConfigManager


def test_menu_item_attributes():
    item = MenuItem(
        id="test_id",
        label="Test Label",
        icon="⚡",
        description="Test description",
        badge="ACTIVE",
    )
    assert item.id == "test_id"
    assert item.label == "Test Label"
    assert item.icon == "⚡"
    assert item.badge == "ACTIVE"


def test_run_menu_arrow_navigation():
    items = [
        MenuItem(id="opt1", label="Option 1"),
        MenuItem(id="opt2", label="Option 2"),
        MenuItem(id="opt3", label="Option 3"),
    ]

    # Navigate down once, then press Enter -> selects opt2
    with patch("clirobot.tui.menu.is_keyboard_supported", return_value=True), \
         patch("clirobot.tui.menu.read_key", side_effect=["down", "enter"]):
        selected = run_menu("Test Menu", "Subtitle", items)
        assert selected is not None
        assert selected.id == "opt2"

    # Press Esc -> returns None
    with patch("clirobot.tui.menu.is_keyboard_supported", return_value=True), \
         patch("clirobot.tui.menu.read_key", side_effect=["esc"]):
        selected = run_menu("Test Menu", "Subtitle", items)
        assert selected is None


def test_fallback_number_selection():
    items = [
        MenuItem(id="opt1", label="Option 1"),
        MenuItem(id="opt2", label="Option 2"),
    ]

    with patch("rich.prompt.Prompt.ask", return_value="2"):
        selected = _fallback_number_selection("Title", "Subtitle", items)
        assert selected is not None
        assert selected.id == "opt2"

    with patch("rich.prompt.Prompt.ask", return_value="0"):
        selected = _fallback_number_selection("Title", "Subtitle", items)
        assert selected is None


def test_tui_app_initialization(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    mgr = ConfigManager(config_path=cfg_file)
    app = TUIApp(config_manager=mgr)

    assert app.mgr.get_active_profile().name == "default"
    assert app.runner is not None
