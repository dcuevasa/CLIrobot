"""CLI subcommands for camera discovery, testing, snapshot preview, and assignment."""

import typer
from typing import Optional, List
from clirobot.config.manager import ConfigManager
from clirobot.hardware.cameras import scan_cameras, display_cameras_table, capture_snapshot_preview, run_interactive_camera_wizard
from clirobot.integration.runner import CommandRunner
from clirobot.ui.console import console, print_success, print_info

app = typer.Typer(help="Discover, test, preview, and configure cameras.", no_args_is_help=False)


@app.callback(invoke_without_command=True)
def default_cameras_action(ctx: typer.Context):
    """List cameras when run without subcommand."""
    if ctx.invoked_subcommand is None:
        list_cameras()


@app.command("list")
@app.command("scan")
def list_cameras():
    """Scan and list all detected video capture devices."""
    mgr = ConfigManager()
    profile = mgr.get_active_profile()
    cams = scan_cameras(active_cameras=profile.cameras)
    display_cameras_table(cams)


@app.command("wizard")
def wizard():
    """Launch interactive camera setup and preview wizard."""
    mgr = ConfigManager()
    run_interactive_camera_wizard(mgr)


@app.command("preview")
def preview(
    camera_index: int = typer.Argument(0, help="Camera index to preview"),
    cols: int = typer.Option(60, "--cols", "-c", help="Terminal character width for ASCII preview"),
):
    """Capture a snapshot and preview it directly in the terminal."""
    preview_text = capture_snapshot_preview(camera_index, width_cols=cols)
    if preview_text:
        console.print(f"\n[bold green]Preview for Camera #{camera_index}:[/bold green]\n")
        console.print(preview_text)


@app.command("find")
def find_cameras_raw(
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect command without executing"),
    extra: Optional[List[str]] = typer.Argument(None, help="Additional arguments passed to LeRobot"),
):
    """Run official lerobot-find-cameras command."""
    mgr = ConfigManager()
    runner = CommandRunner(mgr)
    runner.run("find-cameras", extra or [], dry_run=dry_run)


@app.command("assign")
def assign_camera(
    role: str = typer.Argument(..., help="Role name (e.g. laptop, wrist, overhead, phone)"),
    index_or_path: str = typer.Argument(..., help="Camera index (e.g. 0, 1) or /dev/video* path"),
    width: int = typer.Option(640, "--width", "-w", help="Frame width"),
    height: int = typer.Option(480, "--height", "-h", help="Frame height"),
    fps: int = typer.Option(30, "--fps", help="Target FPS"),
):
    """Assign a camera index or path to a role in the active profile."""
    mgr = ConfigManager()
    profile = mgr.get_active_profile()
    mgr.update_camera(role, index_or_path, width=width, height=height, fps=fps)
    print_success(f"Assigned camera '{role}' -> '{index_or_path}' ({width}x{height} @ {fps}fps) in profile '{profile.name}'.")


@app.command("remove")
def remove_camera(role: str = typer.Argument(..., help="Role name to remove (e.g. wrist)")):
    """Remove a camera from the active profile."""
    mgr = ConfigManager()
    profile = mgr.get_active_profile()
    if mgr.remove_camera(role):
        print_success(f"Removed camera '{role}' from profile '{profile.name}'.")
    else:
        print_info(f"Camera '{role}' was not found in profile '{profile.name}'.")
