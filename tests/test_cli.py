import pytest
from pathlib import Path
from typer.testing import CliRunner
from clirobot.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_config(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "test_config.json"
    monkeypatch.setenv("CLIROBOT_CONFIG_FILE", str(cfg_file))
    yield cfg_file



def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "CLIrobot version" in result.stdout


def test_cli_doctor():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "System Diagnostics & Health Check" in result.stdout


def test_cli_profile_workflow():
    # List profiles
    result = runner.invoke(app, ["profile", "list"])
    assert result.exit_code == 0
    assert "default" in result.stdout

    # Show active profile
    result = runner.invoke(app, ["profile", "show"])
    assert result.exit_code == 0
    assert "Profile: default" in result.stdout

    # Create new profile
    result = runner.invoke(app, ["profile", "create", "test-arm-2", "--notes", "Testing"], input="y\n")
    assert result.exit_code == 0
    assert "Created profile" in result.stdout

    # Switch back to default
    result = runner.invoke(app, ["profile", "switch", "default"])
    assert result.exit_code == 0
    assert "Switched active profile" in result.stdout


def test_cli_ports_commands():
    result = runner.invoke(app, ["ports", "list"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["ports", "assign", "--leader", "/dev/ttyACM0", "--follower", "/dev/ttyACM1"])
    assert result.exit_code == 0
    assert "Updated profile" in result.stdout
    assert "/dev/ttyACM0" in result.stdout


def test_cli_dry_run_commands():
    # Teleop dry-run
    result = runner.invoke(app, ["teleop", "--dry-run"])
    assert result.exit_code == 0
    assert "DRY RUN: teleoperate" in result.stdout

    # Record dry-run
    result = runner.invoke(app, ["record", "--dry-run", "--episodes", "3"])
    assert result.exit_code == 0
    assert "DRY RUN: record" in result.stdout

    # Replay dry-run
    result = runner.invoke(app, ["replay", "--dry-run", "--episode", "2"])
    assert result.exit_code == 0
    assert "DRY RUN: replay" in result.stdout

    # Train dry-run
    result = runner.invoke(app, ["train", "--dry-run", "--dataset", "lerobot/test", "--policy", "act"])
    assert result.exit_code == 0
    assert "DRY RUN: train" in result.stdout

    # Calibrate dry-run
    result = runner.invoke(app, ["calibrate", "run", "--dry-run", "--arm", "follower"])
    assert result.exit_code == 0
    assert "DRY RUN: calibrate" in result.stdout
