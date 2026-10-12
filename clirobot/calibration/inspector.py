"""Visual inspection and diffing for LeRobot calibration files."""

from rich.table import Table
from clirobot.ui.console import console, create_table, print_info, print_warning
from clirobot.calibration.manager import CalibrationFileInfo


def inspect_calibration(info: CalibrationFileInfo) -> None:
    """Print an exhaustive, beautiful visual table of joint calibration values."""
    console.print(f"\n[bold cyan]Calibration Inspection:[/bold cyan] [bold green]{info.robot_type}/{info.robot_id}[/bold green]")
    console.print(f"[dim]Path: {info.path}[/dim]")
    console.print(f"[dim]Modified: {info.modified_time.strftime('%Y-%m-%d %H:%M:%S')}  |  Size: {info.size_bytes} bytes[/dim]\n")

    data = info.data
    if not isinstance(data, dict):
        console.print("[yellow]Invalid or non-dictionary calibration JSON structure.[/yellow]")
        return

    table = create_table(
        f"Joints & Actuators Calibration ({info.robot_id})",
        ["Joint / Motor", "Homing Offset", "Start Pos", "End Pos", "Range (Ticks)", "Calibrated", "Drive Mode"],
    )

    for joint_name, params in data.items():
        if not isinstance(params, dict):
            continue

        homing = str(params.get("homing_offset", params.get("zero_pos", "N/A")))
        start = str(params.get("start_pos", params.get("min_pos", "N/A")))
        end = str(params.get("end_pos", params.get("max_pos", "N/A")))
        drive_mode = str(params.get("drive_mode", "N/A"))
        calibrated = params.get("calibrated", True)
        calib_str = "[bold green]Yes[/bold green]" if calibrated else "[bold yellow]No[/bold yellow]"

        # Calculate range
        try:
            s_val = int(start)
            e_val = int(end)
            range_val = abs(e_val - s_val)
            range_str = f"{range_val:,}"
        except (ValueError, TypeError):
            range_str = "[dim]N/A[/dim]"

        table.add_row(
            f"[bold cyan]{joint_name}[/bold cyan]",
            f"[yellow]{homing}[/yellow]",
            start,
            end,
            range_str,
            calib_str,
            drive_mode,
        )

    console.print(table)


def diff_calibrations(info_a: CalibrationFileInfo, info_b: CalibrationFileInfo) -> None:
    """Compare two calibration files side-by-side with joint difference highlights."""
    console.print(f"\n[bold cyan]Calibration Diff:[/bold cyan]")
    console.print(f"  [cyan]File A:[/cyan] {info_a.robot_type}/{info_a.robot_id} ({info_a.path.name})")
    console.print(f"  [magenta]File B:[/magenta] {info_b.robot_type}/{info_b.robot_id} ({info_b.path.name})\n")

    data_a = info_a.data if isinstance(info_a.data, dict) else {}
    data_b = info_b.data if isinstance(info_b.data, dict) else {}

    all_joints = sorted(set(data_a.keys()) | set(data_b.keys()))

    table = create_table(
        "Joint Comparison",
        ["Joint", "Offset A", "Offset B", "Δ Offset", "Range A", "Range B", "Δ Range"],
    )

    for joint in all_joints:
        ja = data_a.get(joint, {})
        jb = data_b.get(joint, {})

        offset_a = ja.get("homing_offset", ja.get("zero_pos"))
        offset_b = jb.get("homing_offset", jb.get("zero_pos"))

        # Calculate offset delta
        if offset_a is not None and offset_b is not None:
            try:
                diff_offset = int(offset_b) - int(offset_a)
                diff_offset_str = f"[green]+{diff_offset}[/green]" if diff_offset > 0 else (f"[red]{diff_offset}[/red]" if diff_offset < 0 else "[dim]0[/dim]")
            except (ValueError, TypeError):
                diff_offset_str = "[dim]N/A[/dim]"
        else:
            diff_offset_str = "[yellow]Missing[/yellow]"

        # Calculate range A and B
        range_a, range_b = None, None
        try:
            range_a = abs(int(ja.get("end_pos", 0)) - int(ja.get("start_pos", 0)))
        except (ValueError, TypeError):
            pass

        try:
            range_b = abs(int(jb.get("end_pos", 0)) - int(jb.get("start_pos", 0)))
        except (ValueError, TypeError):
            pass

        if range_a is not None and range_b is not None:
            diff_range = range_b - range_a
            diff_range_str = f"[green]+{diff_range}[/green]" if diff_range > 0 else (f"[red]{diff_range}[/red]" if diff_range < 0 else "[dim]0[/dim]")
        else:
            diff_range_str = "[dim]N/A[/dim]"

        table.add_row(
            f"[bold cyan]{joint}[/bold cyan]",
            str(offset_a) if offset_a is not None else "[dim]N/A[/dim]",
            str(offset_b) if offset_b is not None else "[dim]N/A[/dim]",
            diff_offset_str,
            str(range_a) if range_a is not None else "[dim]N/A[/dim]",
            str(range_b) if range_b is not None else "[dim]N/A[/dim]",
            diff_range_str,
        )

    console.print(table)
