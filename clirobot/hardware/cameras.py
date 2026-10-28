"""Camera discovery, hardware testing, terminal snapshot preview, and profile assignment."""

import glob
import os
import sys
import time
from dataclasses import dataclass
from typing import Any
from clirobot.ui.console import console, print_info, print_success, print_warning, print_error, print_step, create_table
from clirobot.ui.prompts import prompt_select, prompt_confirm, prompt_text
from clirobot.config.manager import ConfigManager


@dataclass
class CameraInfo:
    """Camera device information."""
    index: int
    v4l2_path: str | None
    name: str
    available: bool
    width: int = 0
    height: int = 0
    fps: float = 0.0
    backend: str = "opencv"
    assigned_role: str | None = None


def scan_cameras(max_indices: int = 8, active_cameras: dict[str, Any] | None = None) -> list[CameraInfo]:
    """Scan for connected video capture devices."""
    results: list[CameraInfo] = []
    active_cameras = active_cameras or {}
    
    # Invert active cameras mapping for role lookup
    index_to_role = {}
    for role, cam in active_cameras.items():
        idx_str = str(getattr(cam, "index_or_path", cam) if hasattr(cam, "index_or_path") else cam)
        index_to_role[idx_str] = role

    # Check Linux /dev/video* devices if available
    v4l2_devices = sorted(glob.glob("/dev/video*"))

    # Set OpenCV log level to silent to prevent stderr pollution
    os.environ["OPENCV_LOG_LEVEL"] = "OFF"

    try:
        import cv2
        # If on Linux and no /dev/video* devices exist, don't query 0..8 to avoid stderr spam
        if sys.platform.startswith("linux") and not v4l2_devices:
            return results

        for idx in range(max_indices):
            # If on Linux, only query if /dev/video{idx} exists
            if sys.platform.startswith("linux") and f"/dev/video{idx}" not in v4l2_devices:
                continue

            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                ret, frame = cap.read()
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                cap.release()

                v4l2_path = f"/dev/video{idx}" if f"/dev/video{idx}" in v4l2_devices else None
                role = index_to_role.get(str(idx)) or (index_to_role.get(v4l2_path) if v4l2_path else None)

                results.append(
                    CameraInfo(
                        index=idx,
                        v4l2_path=v4l2_path,
                        name=f"Camera #{idx} ({'Functional' if ret else 'Busy/No Signal'})",
                        available=ret,
                        width=w,
                        height=h,
                        fps=fps,
                        assigned_role=role,
                    )
                )
    except ImportError:

        # Fallback if cv2 is not installed
        for idx, dev in enumerate(v4l2_devices):
            role = index_to_role.get(str(idx)) or index_to_role.get(dev)
            results.append(
                CameraInfo(
                    index=idx,
                    v4l2_path=dev,
                    name=f"V4L2 Device ({dev})",
                    available=True,
                    assigned_role=role,
                )
            )

    return results


def display_cameras_table(cameras: list[CameraInfo]) -> None:
    """Render a styled table of detected cameras."""
    table = create_table("Detected Camera Devices", ["Index", "Path", "Status", "Resolution", "Role (Profile)"])
    if not cameras:
        console.print("[yellow]No cameras detected or accessible.[/yellow]")
        return

    for c in cameras:
        status_str = "[bold green]Online[/bold green]" if c.available else "[bold red]Offline / In Use[/bold red]"
        res_str = f"{c.width}x{c.height}" if c.width and c.height else "[dim]Unknown[/dim]"
        role_str = f"[bold green]{c.assigned_role}[/bold green]" if c.assigned_role else "[dim]Unassigned[/dim]"
        path_str = c.v4l2_path or f"/dev/video{c.index}"

        table.add_row(
            f"[bold cyan]{c.index}[/bold cyan]",
            path_str,
            status_str,
            res_str,
            role_str,
        )
    console.print(table)


def capture_snapshot_preview(camera_index: int, width_cols: int = 60) -> str | None:
    """Capture a single frame and convert to terminal ASCII/ANSI art for instant visual confirmation."""
    try:
        import cv2
    except ImportError:
        print_warning("OpenCV is not installed. Snapshot preview unavailable.")
        return None

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print_error(f"Cannot open camera index {camera_index}")
        return None

    # Discard first few frames to allow auto-exposure to stabilize
    for _ in range(3):
        cap.read()
    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        print_error("Failed to grab image frame from camera.")
        return None

    # Save to temporary snapshot file
    out_path = f"/tmp/clirobot_cam_{camera_index}.jpg"
    cv2.imwrite(out_path, frame)

    # Convert to grayscale ASCII preview
    h, w = frame.shape[:2]
    aspect_ratio = h / w
    preview_height = int(width_cols * aspect_ratio * 0.5)  # 0.5 font aspect ratio compensation
    if preview_height < 5:
        preview_height = 10

    small = cv2.resize(frame, (width_cols, preview_height))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    ascii_chars = " .:-=+*#%@"
    ascii_lines = []
    for row in gray:
        line = "".join(ascii_chars[min(val * len(ascii_chars) // 256, len(ascii_chars) - 1)] for val in row)
        ascii_lines.append(line)

    ascii_art = "\n".join(ascii_lines)
    return f"{ascii_art}\n\n[dim]Snapshot saved to: {out_path}[/dim]"


def run_interactive_camera_wizard(config_manager: ConfigManager) -> None:
    """Interactive wizard to discover, preview, and assign camera roles."""
    profile = config_manager.get_active_profile()
    console.print(f"\n[bold cyan]📷 Interactive Camera Setup Wizard (Profile: [green]{profile.name}[/green])[/bold cyan]\n")

    cams = scan_cameras(active_cameras=profile.cameras)
    display_cameras_table(cams)

    if not cams:
        print_warning("No cameras were detected.")
        if prompt_confirm("Do you want to manually enter a camera index/path?"):
            name = prompt_text("Enter camera role name (e.g. laptop, wrist, overhead):", default="laptop")
            idx = prompt_text("Enter camera index or /dev/video* path:", default="0")
            config_manager.update_camera(name, idx)
            print_success(f"Added camera '{name}' with target '{idx}' to profile '{profile.name}'.")
        return

    choice = prompt_select(
        "Camera Action:",
        choices=[
            "Preview Camera Snapshot (Terminal visual verification)",
            "Assign Camera to Role (e.g. laptop, wrist, overhead)",
            "Remove Camera from Profile",
            "Done",
        ],
        default="Preview Camera Snapshot (Terminal visual verification)",
    )

    if choice.startswith("Preview"):
        cam_indices = [str(c.index) for c in cams if c.available]
        if not cam_indices:
            print_warning("No functional cameras to preview.")
            return
        idx_str = prompt_select("Select camera index to preview:", cam_indices, default=cam_indices[0])
        preview = capture_snapshot_preview(int(idx_str))
        if preview:
            console.print(f"\n[bold green]Preview for Camera #{idx_str}:[/bold green]\n")
            console.print(preview)

    elif choice.startswith("Assign"):
        cam_indices = [str(c.index) for c in cams]
        idx_str = prompt_select("Select camera index to assign:", cam_indices, default=cam_indices[0])
        role = prompt_select(
            "Assign to role:",
            choices=["laptop", "wrist", "overhead", "phone", "cam_high", "cam_low", "Custom..."],
            default="wrist",
        )
        if role == "Custom...":
            role = prompt_text("Enter custom camera role name:")

        config_manager.update_camera(role, idx_str)
        print_success(f"Assigned Camera #{idx_str} to role '{role}' in profile '{profile.name}'!")

    elif choice.startswith("Remove"):
        if not profile.cameras:
            print_info("No cameras currently configured in profile.")
            return
        role_to_remove = prompt_select("Select camera to remove:", list(profile.cameras.keys()))
        config_manager.remove_camera(role_to_remove)
        print_success(f"Removed camera '{role_to_remove}' from profile '{profile.name}'.")
