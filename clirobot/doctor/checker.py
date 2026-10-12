"""Comprehensive system diagnostics and environment health check."""

import os
import sys
import shutil
import glob
from dataclasses import dataclass
from typing import Literal
from rich.table import Table
from rich.panel import Panel
from clirobot.ui.console import console, create_table
from clirobot.config.manager import ConfigManager
from clirobot.constants import HF_CACHE_DIR, LEROBOT_BINARIES_MAP
from clirobot.hardware.ports import get_available_ports
from clirobot.hardware.cameras import scan_cameras
from clirobot.keyboard.terminal import TERMIOS_AVAILABLE


@dataclass
class CheckItem:
    """A diagnostic check result."""
    category: str
    name: str
    status: Literal["PASS", "WARN", "FAIL"]
    detail: str
    recommendation: str = ""


def run_doctor_checks() -> list[CheckItem]:
    """Execute all diagnostic checks."""
    checks: list[CheckItem] = []

    # 1. Python Check
    py_ver = sys.version_info
    py_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    if py_ver >= (3, 10):
        checks.append(CheckItem("Python", "Python Version", "PASS", f"{py_str} (Compatible)"))
    else:
        checks.append(CheckItem("Python", "Python Version", "FAIL", f"{py_str} (< 3.10)", "Upgrade to Python >= 3.10"))

    # 2. LeRobot Check
    lerobot_found = False
    lerobot_detail = "Not installed"
    try:
        import lerobot
        lerobot_found = True
        lerobot_detail = f"Installed (v{getattr(lerobot, '__version__', 'unknown')})"
    except ImportError:
        # Check binaries in PATH
        found_bins = [b for b in ["lerobot-record", "lerobot-teleoperate", "lerobot-find-port"] if shutil.which(b)]
        if found_bins:
            lerobot_found = True
            lerobot_detail = f"Found binaries in PATH ({', '.join(found_bins)})"

    if lerobot_found:
        checks.append(CheckItem("LeRobot", "LeRobot Core", "PASS", lerobot_detail))
    else:
        checks.append(
            CheckItem(
                "LeRobot",
                "LeRobot Core",
                "WARN",
                "lerobot package / binaries not found in current environment",
                "Run: pip install lerobot (or pip install 'lerobot[feetech]')",
            )
        )

    # 3. Hardware: Serial Ports & Permissions
    ports = get_available_ports()
    if ports:
        checks.append(CheckItem("Hardware", "Serial Ports", "PASS", f"{len(ports)} port(s) detected"))
    else:
        checks.append(CheckItem("Hardware", "Serial Ports", "WARN", "No USB serial ports detected", "Plug in your robot arm USB cables"))

    # Linux dialout group check
    if sys.platform.startswith("linux"):
        import grp
        user = os.environ.get("USER", "")
        try:
            dialout_members = grp.getgrnam("dialout").gr_mem
            if user in dialout_members or os.getuid() == 0:
                checks.append(CheckItem("Permissions", "Serial Access (dialout)", "PASS", "User has serial port access"))
            else:
                checks.append(
                    CheckItem(
                        "Permissions",
                        "Serial Access (dialout)",
                        "WARN",
                        f"User '{user}' not in 'dialout' group",
                        "Run: sudo usermod -aG dialout $USER && newgrp dialout",
                    )
                )
        except Exception:
            pass

    # 4. Hardware: Cameras
    cams = scan_cameras(max_indices=4)
    active_cams = [c for c in cams if c.available]
    if active_cams:
        checks.append(CheckItem("Hardware", "Cameras", "PASS", f"{len(active_cams)} camera(s) accessible"))
    else:
        checks.append(CheckItem("Hardware", "Cameras", "WARN", "No functional video capture devices found", "Connect USB webcam / camera"))

    # 5. Keyboard Capabilities
    if sys.stdin.isatty():
        checks.append(CheckItem("Keyboard", "TTY Stdin", "PASS", "Interactive TTY terminal active"))
    else:
        checks.append(CheckItem("Keyboard", "TTY Stdin", "WARN", "Non-interactive / piped stdin", "Run in an interactive terminal"))

    if TERMIOS_AVAILABLE:
        checks.append(CheckItem("Keyboard", "Termios Raw Mode", "PASS", "POSIX terminal raw mode supported"))
    else:
        checks.append(CheckItem("Keyboard", "Termios Raw Mode", "WARN", "Termios not available on this platform"))

    # Display / GUI check
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    checks.append(
        CheckItem(
            "Display",
            "GUI Display",
            "PASS" if has_display else "WARN",
            f"DISPLAY={os.environ.get('DISPLAY', 'None')}",
            "If using OpenCV camera windows, ensure X11/Wayland display is forwarded",
        )
    )

    # 6. Active Profile Check
    mgr = ConfigManager()
    profile = mgr.get_active_profile()
    if profile.leader_arm.port and profile.follower_arm.port:
        checks.append(CheckItem("Profile", f"Active Profile ({profile.name})", "PASS", "Leader and Follower ports configured"))
    elif profile.leader_arm.port or profile.follower_arm.port:
        checks.append(CheckItem("Profile", f"Active Profile ({profile.name})", "WARN", "Only one arm port configured", "Run 'clirobot ports find'"))
    else:
        checks.append(CheckItem("Profile", f"Active Profile ({profile.name})", "WARN", "No ports configured in profile", "Run 'clirobot ports find'"))

    # 7. Cache Directory
    cache_dir = HF_CACHE_DIR
    if cache_dir.exists() and os.access(cache_dir, os.W_OK):
        checks.append(CheckItem("Cache", "LeRobot Cache", "PASS", f"Writable ({cache_dir})"))
    else:
        checks.append(CheckItem("Cache", "LeRobot Cache", "PASS", f"Ready ({cache_dir})"))

    return checks


def display_doctor_report() -> None:
    """Run all checks and render a styled report."""
    console.print("\n[bold cyan]⚡ CLIrobot System Diagnostics & Health Check[/bold cyan]\n")

    checks = run_doctor_checks()

    table = create_table("Diagnostic Results", ["Subsystem", "Check", "Status", "Details"])
    recommendations: list[str] = []

    for item in checks:
        if item.status == "PASS":
            status_badge = "[bold green]PASS[/bold green]"
        elif item.status == "WARN":
            status_badge = "[bold yellow]WARN[/bold yellow]"
            if item.recommendation:
                recommendations.append(f"• [bold yellow]{item.name}:[/bold yellow] {item.recommendation}")
        else:
            status_badge = "[bold red]FAIL[/bold red]"
            if item.recommendation:
                recommendations.append(f"• [bold red]{item.name}:[/bold red] {item.recommendation}")

        table.add_row(
            f"[bold cyan]{item.category}[/bold cyan]",
            item.name,
            status_badge,
            item.detail,
        )

    console.print(table)

    if recommendations:
        rec_panel = Panel(
            "\n".join(recommendations),
            title="[bold yellow]Recommended Actions[/bold yellow]",
            border_style="yellow",
            padding=(1, 2),
        )
        console.print(rec_panel)
    else:
        console.print("[bold green]✔ All systems operational! Ready to control robots.[/bold green]\n")
