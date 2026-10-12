"""Serial port discovery, live plug/unplug detection, and profile assignment."""

import time
from dataclasses import dataclass
from typing import Callable
import serial.tools.list_ports
from clirobot.ui.console import console, print_step, print_success, print_info, print_warning, create_table
from clirobot.ui.prompts import prompt_confirm, prompt_select
from clirobot.config.manager import ConfigManager


@dataclass
class SerialPortInfo:
    """Detailed serial port metadata."""
    device: str
    description: str
    hardware_id: str
    vid: int | None = None
    pid: int | None = None
    serial_number: str | None = None
    assigned_role: str | None = None


def get_available_ports(
    active_leader_port: str = "",
    active_follower_port: str = "",
    include_all: bool = False,
) -> list[SerialPortInfo]:
    """Scan and list all currently accessible serial ports, prioritizing USB devices."""
    ports = serial.tools.list_ports.comports()
    results: list[SerialPortInfo] = []

    for p in ports:
        role = None
        if p.device == active_leader_port:
            role = "Leader"
        elif p.device == active_follower_port:
            role = "Follower"

        # Filter out inactive motherboard /dev/ttyS* ports unless assigned or explicitly requested
        is_platform_ttys = p.device.startswith("/dev/ttyS") and not p.device.startswith("/dev/ttySpeed")
        if is_platform_ttys and not role and not include_all and p.vid is None:
            continue

        results.append(
            SerialPortInfo(
                device=p.device,
                description=p.description or "Unknown Serial Device",
                hardware_id=p.hwid or "",
                vid=p.vid,
                pid=p.pid,
                serial_number=p.serial_number,
                assigned_role=role,
            )
        )

    # Sort USB / ACM / assigned devices first
    def sort_key(item: SerialPortInfo) -> tuple[int, str]:
        is_assigned = 0 if item.assigned_role else 1
        is_usb = 0 if any(k in item.device.lower() for k in ("usb", "acm", "com")) or item.vid is not None else 2
        return (is_assigned, is_usb, item.device)

    return sorted(results, key=sort_key)



def display_ports_table(ports: list[SerialPortInfo]) -> None:
    """Render a styled table of all detected serial ports."""
    table = create_table("Detected Serial / USB Ports", ["Device", "Description", "Role (Profile)", "VID:PID", "Serial Number"])
    if not ports:
        console.print("[yellow]No serial ports detected on the system.[/yellow]")
        return

    for p in ports:
        role_str = f"[bold green]{p.assigned_role}[/bold green]" if p.assigned_role else "[dim]Unassigned[/dim]"
        vid_pid = f"{p.vid:04x}:{p.pid:04x}" if p.vid and p.pid else "[dim]N/A[/dim]"
        serial_str = p.serial_number or "[dim]N/A[/dim]"
        table.add_row(
            f"[bold cyan]{p.device}[/bold cyan]",
            p.description,
            role_str,
            vid_pid,
            serial_str,
        )
    console.print(table)


def wait_for_port_change(
    timeout_seconds: float = 30.0,
    check_interval: float = 0.5,
    on_tick: Callable[[float], None] | None = None,
) -> tuple[set[str], set[str]]:
    """Monitor serial ports for connect or disconnect events.
    
    Returns:
        (added_ports, removed_ports) sets of device paths.
    """
    initial_devices = {p.device for p in serial.tools.list_ports.comports()}
    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        current_devices = {p.device for p in serial.tools.list_ports.comports()}
        added = current_devices - initial_devices
        removed = initial_devices - current_devices

        if added or removed:
            return added, removed

        remaining = timeout_seconds - (time.time() - start_time)
        if on_tick:
            on_tick(remaining)
        time.sleep(check_interval)

    return set(), set()


def run_interactive_port_wizard(config_manager: ConfigManager) -> None:
    """Guided wizard to detect leader & follower arms via interactive plug-in detection."""
    profile = config_manager.get_active_profile()
    console.print(f"\n[bold cyan]⚡ Interactive Port Assignment Wizard (Profile: [green]{profile.name}[/green])[/bold cyan]")
    console.print("[dim]This wizard helps you identify and save USB ports for your robot arms.[/dim]\n")

    current_ports = get_available_ports(profile.leader_arm.port, profile.follower_arm.port)
    display_ports_table(current_ports)

    mode = prompt_select(
        "Choose Assignment Mode:",
        choices=[
            "Plug-and-Detect (Recommended: Unplug & replug USB cables)",
            "Manual Port Selection (Pick from detected ports list)",
            "Cancel",
        ],
        default="Plug-and-Detect (Recommended: Unplug & replug USB cables)",
    )

    if mode.startswith("Cancel"):
        print_info("Wizard cancelled.")
        return

    if mode.startswith("Manual"):
        _manual_port_assignment(config_manager, current_ports)
        return

    # Plug-and-Detect Mode
    console.print("\n[bold yellow]Step 1: Identifying the LEADER arm[/bold yellow]")
    print_info("If the Leader arm is currently plugged in, UNPLUG its USB cable now.")
    prompt_confirm("Press Enter when Leader arm is disconnected...", default=True)

    baseline = {p.device for p in serial.tools.list_ports.comports()}
    print_step("Now, PLUG IN the LEADER arm USB cable...")
    console.print("[dim]Waiting for device connection (30s timeout)...[/dim]")

    added, _ = wait_for_port_change(timeout_seconds=30.0)
    if not added:
        print_warning("No new USB connection detected within 30 seconds.")
        if prompt_confirm("Would you like to manually pick the Leader port?"):
            _manual_port_assignment(config_manager, get_available_ports(), target="leader")
    else:
        leader_port = next(iter(added))
        print_success(f"Detected Leader Arm at: [bold green]{leader_port}[/bold green]")
        config_manager.update_ports(leader_port=leader_port)
        print_success(f"Saved Leader port '{leader_port}' to profile '{profile.name}'!")

    console.print("\n[bold yellow]Step 2: Identifying the FOLLOWER arm[/bold yellow]")
    print_info("If the Follower arm is currently plugged in, UNPLUG its USB cable now.")
    prompt_confirm("Press Enter when Follower arm is disconnected...", default=True)

    print_step("Now, PLUG IN the FOLLOWER arm USB cable...")
    console.print("[dim]Waiting for device connection (30s timeout)...[/dim]")

    added, _ = wait_for_port_change(timeout_seconds=30.0)
    if not added:
        print_warning("No new USB connection detected within 30 seconds.")
        if prompt_confirm("Would you like to manually pick the Follower port?"):
            _manual_port_assignment(config_manager, get_available_ports(), target="follower")
    else:
        follower_port = next(iter(added))
        print_success(f"Detected Follower Arm at: [bold green]{follower_port}[/bold green]")
        config_manager.update_ports(follower_port=follower_port)
        print_success(f"Saved Follower port '{follower_port}' to profile '{profile.name}'!")

    console.print("\n[bold green]✔ Port configuration complete![/bold green]")
    updated = config_manager.get_active_profile()
    console.print(f"  • Leader Port:   [bold cyan]{updated.leader_arm.port or 'Not set'}[/bold cyan]")
    console.print(f"  • Follower Port: [bold cyan]{updated.follower_arm.port or 'Not set'}[/bold cyan]\n")


def _manual_port_assignment(
    config_manager: ConfigManager,
    ports: list[SerialPortInfo],
    target: str | None = None,
) -> None:
    """Manually assign ports from list to leader and/or follower."""
    if not ports:
        print_warning("No serial ports found to select from.")
        return

    choices = [p.device for p in ports]

    if target in (None, "leader"):
        console.print("\n[bold cyan]Select Leader Arm Port:[/bold cyan]")
        leader_choice = prompt_select("Leader Port", choices + ["Skip"], default="Skip")
        if leader_choice != "Skip":
            config_manager.update_ports(leader_port=leader_choice)
            print_success(f"Updated Leader port to {leader_choice}")

    if target in (None, "follower"):
        console.print("\n[bold cyan]Select Follower Arm Port:[/bold cyan]")
        follower_choice = prompt_select("Follower Port", choices + ["Skip"], default="Skip")
        if follower_choice != "Skip":
            config_manager.update_ports(follower_port=follower_choice)
            print_success(f"Updated Follower port to {follower_choice}")
