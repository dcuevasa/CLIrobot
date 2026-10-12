"""Udev rules generation for permanent, predictable robot arm USB symlinks on Linux."""

import os
from pathlib import Path
import serial.tools.list_ports
from clirobot.ui.console import console, print_info, print_success, print_warning
from clirobot.config.manager import ConfigManager


def generate_udev_rules(config_manager: ConfigManager) -> str:
    """Generate udev rules content mapping current arm serial IDs to stable symlinks."""
    profile = config_manager.get_active_profile()
    comports = {p.device: p for p in serial.tools.list_ports.comports()}
    
    lines = [
        "# CLIrobot / LeRobot Permanent USB Device Rules",
        "# Generated automatically by CLIrobot",
        "# Allows fixed device symlinks: /dev/lerobot-leader and /dev/lerobot-follower",
        "",
    ]

    leader_port = profile.leader_arm.port
    if leader_port and leader_port in comports:
        p = comports[leader_port]
        if p.serial_number:
            lines.append(
                f'SUBSYSTEM=="tty", ATTRS{{idVendor}}=="{p.vid:04x}", ATTRS{{idProduct}}=="{p.pid:04x}", '
                f'ATTRS{{serial}}=="{p.serial_number}", SYMLINK+="lerobot-leader", MODE="0666"'
            )
        elif p.vid and p.pid:
            lines.append(
                f'SUBSYSTEM=="tty", ATTRS{{idVendor}}=="{p.vid:04x}", ATTRS{{idProduct}}=="{p.pid:04x}", '
                f'SYMLINK+="lerobot-leader", MODE="0666"'
            )

    follower_port = profile.follower_arm.port
    if follower_port and follower_port in comports:
        p = comports[follower_port]
        if p.serial_number:
            lines.append(
                f'SUBSYSTEM=="tty", ATTRS{{idVendor}}=="{p.vid:04x}", ATTRS{{idProduct}}=="{p.pid:04x}", '
                f'ATTRS{{serial}}=="{p.serial_number}", SYMLINK+="lerobot-follower", MODE="0666"'
            )
        elif p.vid and p.pid:
            lines.append(
                f'SUBSYSTEM=="tty", ATTRS{{idVendor}}=="{p.vid:04x}", ATTRS{{idProduct}}=="{p.pid:04x}", '
                f'SYMLINK+="lerobot-follower", MODE="0666"'
            )

    lines.append("")
    return "\n".join(lines)


def print_udev_guide(rules_text: str) -> None:
    """Print instructions on installing the udev rules."""
    console.print("\n[bold cyan]Generated Udev Rules for Permanent Robot Ports:[/bold cyan]")
    console.print(f"[green]{rules_text}[/green]")
    console.print("[dim]To install these rules permanently on Linux, run:[/dim]")
    console.print("[bold yellow]  echo '<RULES>' | sudo tee /etc/udev/rules.d/99-lerobot.rules[/bold yellow]")
    console.print("[bold yellow]  sudo udevadm control --reload-rules && sudo udevadm trigger[/bold yellow]\n")
    console.print("Once reloaded, you can use [bold cyan]/dev/lerobot-leader[/bold cyan] and [bold cyan]/dev/lerobot-follower[/bold cyan] in your profiles!\n")
