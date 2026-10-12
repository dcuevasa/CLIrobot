"""CLI subcommands for robot calibration and calibration file management."""

import typer
from pathlib import Path
from typing import Optional, List
from clirobot.config.manager import ConfigManager
from clirobot.calibration.manager import CalibrationManager
from clirobot.calibration.inspector import inspect_calibration, diff_calibrations
from clirobot.integration.args_builder import LeRobotArgsBuilder
from clirobot.integration.runner import CommandRunner
from clirobot.ui.console import console, print_success, print_info, print_warning, print_error, create_table
from clirobot.ui.prompts import prompt_select, prompt_confirm

app = typer.Typer(help="Manage calibrations and run joint calibration procedures.", no_args_is_help=False)


@app.callback(invoke_without_command=True)
def default_calibrate_action(ctx: typer.Context):
    """List calibrations when run without subcommand."""
    if ctx.invoked_subcommand is None:
        list_calibrations()


@app.command("run")
def run_calibration(
    arm: str = typer.Option("follower", "--arm", "-a", help="Arm to calibrate: 'follower' or 'leader'"),
    robot_type: Optional[str] = typer.Option(None, "--robot-type", help="Override robot type"),
    port: Optional[str] = typer.Option(None, "--port", "-p", help="Override serial port"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Run the official lerobot-calibrate routine with profile defaults pre-configured."""
    mgr = ConfigManager()
    profile = mgr.get_active_profile()

    args = LeRobotArgsBuilder.build_calibrate_args(profile, arm=arm, extra_args=extra)

    # Apply manual overrides if given
    if robot_type:
        args = [a for a in args if not a.startswith("--robot.type=")] + [f"--robot.type={robot_type}"]
    if port:
        args = [a for a in args if not a.startswith("--robot.port=")] + [f"--robot.port={port}"]

    runner = CommandRunner(mgr)
    runner.run("calibrate", args, dry_run=dry_run)


@app.command("list")
def list_calibrations():
    """List all saved calibration files discovered across LeRobot cache directories."""
    cal_mgr = CalibrationManager()
    files = cal_mgr.list_calibrations()

    if not files:
        console.print("[yellow]No calibration files found in LeRobot cache.[/yellow]")
        console.print("[dim]Run 'clirobot calibrate run' to generate calibration for your arm.[/dim]")
        return

    table = create_table("Saved Robot Calibrations", ["Robot Type", "Arm / ID", "Filename", "Modified", "Size"])
    for f in files:
        table.add_row(
            f"[bold cyan]{f.robot_type}[/bold cyan]",
            f"[bold green]{f.robot_id}[/bold green]",
            f.path.name,
            f.modified_time.strftime("%Y-%m-%d %H:%M:%S"),
            f"{f.size_bytes} B",
        )
    console.print(table)


@app.command("inspect")
def inspect_file(
    identifier: Optional[str] = typer.Argument(None, help="Calibration ID, filename, or robot_type/robot_id")
):
    """Visually inspect joint homing offsets, travel limits, and registers in a calibration file."""
    cal_mgr = CalibrationManager()
    files = cal_mgr.list_calibrations()

    if not files:
        print_warning("No calibration files found.")
        return

    if not identifier:
        choices = [f"{f.robot_type}/{f.robot_id}" for f in files]
        identifier = prompt_select("Select calibration file to inspect:", choices)

    info = cal_mgr.get_calibration(identifier)
    if not info:
        print_error(f"Calibration '{identifier}' not found.")
        return

    inspect_calibration(info)


@app.command("backup")
def backup_calibrations(
    identifier: Optional[str] = typer.Option(None, "--id", help="Backup a specific calibration or all if omitted")
):
    """Create a timestamped backup archive of calibration files."""
    cal_mgr = CalibrationManager()
    backed_up = cal_mgr.backup(identifier)
    if backed_up:
        print_success(f"Backed up {len(backed_up)} calibration file(s) to:")
        console.print(f"  [cyan]{backed_up[0].parent}[/cyan]")
    else:
        print_warning("No calibration files to backup.")


@app.command("restore")
def restore_calibrations():
    """Restore calibration files from a previous backup archive."""
    cal_mgr = CalibrationManager()
    backups = cal_mgr.list_backups()

    if not backups:
        print_warning("No backups available to restore.")
        return

    choices = [f"{name} ({len(files)} files)" for name, files in backups]
    selected = prompt_select("Select backup archive to restore:", choices)
    backup_name = selected.split(" ")[0]

    count = cal_mgr.restore_backup(backup_name)
    print_success(f"Successfully restored {count} calibration file(s) from '{backup_name}'!")


@app.command("diff")
def diff_files(
    file_a: Optional[str] = typer.Argument(None, help="First calibration ID or path"),
    file_b: Optional[str] = typer.Argument(None, help="Second calibration ID or path"),
):
    """Compare two calibration files joint by joint."""
    cal_mgr = CalibrationManager()
    files = cal_mgr.list_calibrations()

    if len(files) < 2 and (not file_a or not file_b):
        print_warning("Need at least two calibration files to perform comparison.")
        return

    choices = [f"{f.robot_type}/{f.robot_id}" for f in files]
    if not file_a:
        file_a = prompt_select("Select first calibration (A):", choices)
    if not file_b:
        file_b = prompt_select("Select second calibration (B):", choices)

    info_a = cal_mgr.get_calibration(file_a)
    info_b = cal_mgr.get_calibration(file_b)

    if not info_a or not info_b:
        print_error("One or both calibration files could not be found.")
        return

    diff_calibrations(info_a, info_b)


@app.command("export")
def export_file(
    identifier: str = typer.Argument(..., help="Calibration ID (e.g. so100/main)"),
    dest: Path = typer.Argument(..., help="Destination path or directory"),
):
    """Export a calibration file to share with teammates or move to another machine."""
    cal_mgr = CalibrationManager()
    try:
        out = cal_mgr.export_calibration(identifier, dest)
        print_success(f"Exported calibration to: [bold cyan]{out}[/bold cyan]")
    except Exception as e:
        print_error(f"Export failed: {e}")


@app.command("import")
def import_file(
    source_file: Path = typer.Argument(..., help="Path to external calibration JSON file"),
    robot_type: str = typer.Option("so100", "--robot-type", "-r", help="Robot type"),
    robot_id: str = typer.Option("imported", "--robot-id", "-i", help="Robot ID / arm name"),
):
    """Import an external calibration JSON file into the primary LeRobot cache."""
    cal_mgr = CalibrationManager()
    try:
        out = cal_mgr.import_calibration(source_file, robot_type=robot_type, robot_id=robot_id)
        print_success(f"Imported calibration into cache: [bold cyan]{out}[/bold cyan]")
    except Exception as e:
        print_error(f"Import failed: {e}")
