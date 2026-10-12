"""Main TUI navigation controller and interactive wizards."""

import os
import sys
import time
from pathlib import Path
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from clirobot.ui.console import console, print_success, print_info, print_warning, print_error
from clirobot.config.manager import ConfigManager
from clirobot.constants import SUPPORTED_ROBOTS, SUPPORTED_POLICIES
from clirobot.hardware.ports import get_available_ports, display_ports_table, run_interactive_port_wizard
from clirobot.hardware.cameras import scan_cameras, display_cameras_table, capture_snapshot_preview, run_interactive_camera_wizard
from clirobot.hardware.udev import generate_udev_rules, print_udev_guide
from clirobot.calibration.manager import CalibrationManager
from clirobot.calibration.inspector import inspect_calibration, diff_calibrations
from clirobot.integration.runner import CommandRunner
from clirobot.integration.args_builder import LeRobotArgsBuilder
from clirobot.doctor.checker import display_doctor_report
from clirobot.keyboard.tester import run_keyboard_test
from clirobot.tui.menu import MenuItem, run_menu, clear_terminal


def pause_return_to_menu() -> None:
    """Prompt the user to press Enter before returning to the TUI."""
    console.print("\n[dim]Press [bold yellow]Enter[/bold yellow] to return to the menu...[/dim]")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass


class TUIApp:
    """Main application loop managing interactive menus and hardware wizards."""

    def __init__(self, config_manager: ConfigManager | None = None):
        self.mgr = config_manager or ConfigManager()
        self.runner = CommandRunner(self.mgr)

    def start(self) -> None:
        """Launch the top-level TUI main menu."""
        while True:
            profile = self.mgr.get_active_profile()

            main_items = [
                MenuItem(
                    id="control",
                    label="Robotics Control & Teleop",
                    icon="🎮",
                    description="Launch live teleoperation, demonstration recording, replay, or training.",
                ),
                MenuItem(
                    id="hardware",
                    label="Hardware & Connections",
                    icon="🔌",
                    description="Select USB ports for arms, configure cameras, preview video, and test motors.",
                ),
                MenuItem(
                    id="profiles",
                    label="Profiles & Configuration",
                    icon="👤",
                    description="Switch between saved robot setups, create new profiles, or edit parameters.",
                    badge=f"{profile.name} ({profile.robot_type})",
                ),
                MenuItem(
                    id="calibration",
                    label="Calibration Files Manager",
                    icon="🗜️",
                    description="Visually inspect joint homing offsets, travel ranges, diff calibrations, or backup.",
                ),
                MenuItem(
                    id="datasets",
                    label="Datasets & Visualization",
                    icon="📊",
                    description="Visualize episodes in Rerun, edit datasets, annotate tasks, or build MP4 sidecars.",
                ),
                MenuItem(
                    id="doctor",
                    label="System Doctor Diagnostics",
                    icon="🩺",
                    description="Run full environment health check (Python, LeRobot, serial permissions, cameras).",
                ),
                MenuItem(
                    id="keyboard",
                    label="Keyboard Diagnostics & Latency",
                    icon="⌨️",
                    description="Interactive bench to test raw key capture, arrow keys, and latency.",
                ),
                MenuItem(
                    id="exit",
                    label="Exit CLIrobot",
                    icon="🚪",
                    description="Return to terminal shell.",
                ),
            ]

            choice = run_menu(
                title="Main Menu",
                subtitle="Select an option using arrow keys [↑/↓] and press Enter:",
                items=main_items,
                active_profile=profile,
                breadcrumbs=["Home"],
            )

            if choice is None or choice.id == "exit":
                clear_terminal()
                console.print("[yellow]Exited CLIrobot. Goodbye![/yellow]\n")
                break

            if choice.id == "control":
                self._menu_control()
            elif choice.id == "hardware":
                self._menu_hardware()
            elif choice.id == "profiles":
                self._menu_profiles()
            elif choice.id == "calibration":
                self._menu_calibration()
            elif choice.id == "datasets":
                self._menu_datasets()
            elif choice.id == "doctor":
                clear_terminal()
                display_doctor_report()
                pause_return_to_menu()
            elif choice.id == "keyboard":
                clear_terminal()
                run_keyboard_test()
                pause_return_to_menu()

    # ========================================================================
    # Submenu: Control & Teleoperation
    # ========================================================================

    def _menu_control(self) -> None:
        """Control submenu."""
        while True:
            profile = self.mgr.get_active_profile()

            items = [
                MenuItem(
                    id="teleop",
                    label="Live Teleoperation",
                    icon="⚡",
                    description=f"Control follower arm ({profile.follower_arm.port or 'Not set'}) with leader arm ({profile.leader_arm.port or 'Not set'}).",
                ),
                MenuItem(
                    id="record",
                    label="Record Demonstrations",
                    icon="🔴",
                    description=f"Record episodes into dataset repo '{profile.dataset_repo_id}' at {profile.default_fps} FPS.",
                ),
                MenuItem(
                    id="replay",
                    label="Replay Episode",
                    icon="▶️",
                    description="Replay a recorded episode onto physical follower arm.",
                ),
                MenuItem(
                    id="calibrate",
                    label="Calibrate Robot Arm",
                    icon="📐",
                    description="Run joint calibration procedure for follower or leader arm.",
                ),
                MenuItem(
                    id="train",
                    label="Train Imitation Policy",
                    icon="🧠",
                    description="Train ACT, Diffusion, or SmolVLM policy on recorded dataset.",
                ),
                MenuItem(
                    id="eval",
                    label="Evaluate Policy",
                    icon="🏆",
                    description="Benchmark trained checkpoint on robot arm or in simulation.",
                ),
                MenuItem(
                    id="back",
                    label="Back to Main Menu",
                    icon="↩️",
                    description="Return to previous menu.",
                ),
            ]

            choice = run_menu(
                title="Robotics Control",
                subtitle="Execute teleoperation, recording, calibration, or training:",
                items=items,
                active_profile=profile,
                breadcrumbs=["Home", "Control"],
            )

            if choice is None or choice.id == "back":
                break

            clear_terminal()

            if choice.id == "teleop":
                args = LeRobotArgsBuilder.build_teleoperate_args(profile)
                self.runner.run("teleoperate", args)
                pause_return_to_menu()

            elif choice.id == "record":
                console.print(f"\n[bold cyan]Demonstration Recording Setup ({profile.name})[/bold cyan]\n")
                episodes = int(Prompt.ask("Number of episodes to record", default="10"))
                task = Prompt.ask("Task instruction (optional)", default="")
                
                configure_qol = Confirm.ask("Configure recording QoL options (Rerun viz, streaming encode, sound cues, scene reset)?", default=False)
                display_data = False
                streaming_enc = False
                play_sounds = False
                reset_ep = False
                resume = False

                if configure_qol:
                    display_data = Confirm.ask("  • Launch Rerun live visualizer?", default=True)
                    streaming_enc = Confirm.ask("  • Stream-encode video asynchronously for instant saves?", default=True)
                    play_sounds = Confirm.ask("  • Enable audible voice / sound cues for episode events?", default=False)
                    reset_ep = Confirm.ask("  • Reset robot / environment between episodes?", default=False)
                    resume = Confirm.ask("  • Resume recording into existing dataset?", default=False)

                args = LeRobotArgsBuilder.build_record_args(
                    profile,
                    num_episodes=episodes,
                    single_task=task if task else None,
                    display_data=display_data,
                    streaming_encoding=streaming_enc,
                    play_sounds=play_sounds,
                    reset_every_episode=reset_ep,
                    resume=resume,
                )
                self.runner.run("record", args)
                pause_return_to_menu()

            elif choice.id == "replay":
                console.print(f"\n[bold cyan]Episode Replay ({profile.name})[/bold cyan]\n")
                ep = int(Prompt.ask("Episode index to replay", default="0"))
                args = LeRobotArgsBuilder.build_replay_args(profile, episode=ep)
                self.runner.run("replay", args)
                pause_return_to_menu()

            elif choice.id == "calibrate":
                arm = Prompt.ask("Select arm to calibrate", choices=["follower", "leader"], default="follower")
                args = LeRobotArgsBuilder.build_calibrate_args(profile, arm=arm)
                self.runner.run("calibrate", args)
                pause_return_to_menu()

            elif choice.id == "train":
                repo = Prompt.ask("Dataset repo ID", default=profile.dataset_repo_id)
                policy = Prompt.ask("Policy architecture", choices=SUPPORTED_POLICIES, default="act")
                steps = int(Prompt.ask("Training steps", default="100000"))
                args = LeRobotArgsBuilder.build_train_args(dataset_repo_id=repo, policy_type=policy, steps=steps)
                self.runner.run("train", args)
                pause_return_to_menu()

            elif choice.id == "eval":
                policy_path = Prompt.ask("Policy checkpoint path or HF ID")
                self.runner.run("eval", [f"--policy.path={policy_path}"])
                pause_return_to_menu()

    # ========================================================================
    # Submenu: Hardware & Connections
    # ========================================================================

    def _menu_hardware(self) -> None:
        """Hardware submenu."""
        while True:
            profile = self.mgr.get_active_profile()

            items = [
                MenuItem(
                    id="assign_leader",
                    label="Assign Leader Arm Port",
                    icon="🎮",
                    description=f"Current: {profile.leader_arm.port or 'Not Set'}. Select from detected USB ports.",
                    badge=profile.leader_arm.port or "Unassigned",
                ),
                MenuItem(
                    id="assign_follower",
                    label="Assign Follower Arm Port",
                    icon="🦾",
                    description=f"Current: {profile.follower_arm.port or 'Not Set'}. Select from detected USB ports.",
                    badge=profile.follower_arm.port or "Unassigned",
                ),
                MenuItem(
                    id="port_wizard",
                    label="Plug-and-Detect Port Wizard",
                    icon="⚡",
                    description="Interactive wizard: detects USB plug/unplug events dynamically.",
                ),
                MenuItem(
                    id="list_ports",
                    label="View All Detected Serial Ports",
                    icon="📋",
                    description="Displays detailed table of all USB and serial ports on system.",
                ),
                MenuItem(
                    id="cameras_menu",
                    label="Cameras Setup & Preview",
                    icon="📷",
                    description="Scan cameras, view ASCII snapshot preview, and assign roles (wrist, overhead).",
                    badge=f"{len(profile.cameras)} active",
                ),
                MenuItem(
                    id="setup_motors",
                    label="Motor Bus Setup",
                    icon="⚙️",
                    description="Run lerobot-setup-motors to test servo communication and assign IDs.",
                ),
                MenuItem(
                    id="joint_limits",
                    label="Joint Limits Calibrator",
                    icon="📏",
                    description="Run lerobot-find-joint-limits to discover min/max travel ranges.",
                ),
                MenuItem(
                    id="setup_can",
                    label="CAN Bus Setup",
                    icon="🚌",
                    description="Configure CAN interfaces (slcan, socketcan).",
                ),
                MenuItem(
                    id="udev_rules",
                    label="Generate Linux udev Symlinks",
                    icon="🔒",
                    description="Create permanent symlinks (/dev/lerobot-leader, follower) that never change on reboot.",
                ),
                MenuItem(
                    id="back",
                    label="Back to Main Menu",
                    icon="↩️",
                    description="Return to previous menu.",
                ),
            ]

            choice = run_menu(
                title="Hardware & Connections",
                subtitle="Select a hardware management action:",
                items=items,
                active_profile=profile,
                breadcrumbs=["Home", "Hardware"],
            )

            if choice is None or choice.id == "back":
                break

            clear_terminal()

            if choice.id == "assign_leader":
                self._quick_assign_port("leader")
            elif choice.id == "assign_follower":
                self._quick_assign_port("follower")
            elif choice.id == "port_wizard":
                run_interactive_port_wizard(self.mgr)
                pause_return_to_menu()
            elif choice.id == "list_ports":
                display_ports_table(get_available_ports(profile.leader_arm.port, profile.follower_arm.port))
                pause_return_to_menu()
            elif choice.id == "cameras_menu":
                self._menu_cameras()
            elif choice.id == "setup_motors":
                args = [f"--robot.type={profile.robot_type}"]
                if profile.follower_arm.port:
                    args.append(f"--robot.port={profile.follower_arm.port}")
                self.runner.run("setup-motors", args)
                pause_return_to_menu()
            elif choice.id == "joint_limits":
                args = [f"--robot.type={profile.robot_type}"]
                if profile.follower_arm.port:
                    args.append(f"--robot.port={profile.follower_arm.port}")
                self.runner.run("find-joint-limits", args)
                pause_return_to_menu()
            elif choice.id == "setup_can":
                self.runner.run("setup-can", [])
                pause_return_to_menu()
            elif choice.id == "udev_rules":
                rules = generate_udev_rules(self.mgr)
                print_udev_guide(rules)
                pause_return_to_menu()

    def _quick_assign_port(self, target: str) -> None:
        """Present detected ports as an arrow-key menu for 1-click port selection."""
        profile = self.mgr.get_active_profile()
        ports = get_available_ports(profile.leader_arm.port, profile.follower_arm.port)

        port_items = []
        for p in ports:
            badge = f"VID:{p.vid:04x}" if p.vid else ""
            port_items.append(
                MenuItem(
                    id=p.device,
                    label=p.device,
                    icon="🔌",
                    description=f"{p.description} (Serial: {p.serial_number or 'N/A'})",
                    badge=badge,
                )
            )

        port_items.append(
            MenuItem(
                id="custom",
                label="Enter Custom Path...",
                icon="✍️",
                description="Type path manually (e.g. /dev/lerobot-leader or COM3)",
            )
        )
        port_items.append(
            MenuItem(
                id="back",
                label="Cancel",
                icon="↩️",
                description="Return without changing port.",
            )
        )

        chosen = run_menu(
            title=f"Assign {target.capitalize()} Arm Port",
            subtitle=f"Select device path for {target.capitalize()} arm in profile '{profile.name}':",
            items=port_items,
            active_profile=profile,
            breadcrumbs=["Home", "Hardware", f"Assign {target.capitalize()}"],
        )

        if chosen is None or chosen.id == "back":
            return

        if chosen.id == "custom":
            custom_path = Prompt.ask(f"Enter port path for {target} arm").strip()
            if custom_path:
                if target == "leader":
                    self.mgr.update_ports(leader_port=custom_path)
                else:
                    self.mgr.update_ports(follower_port=custom_path)
                print_success(f"Assigned {target} arm to '{custom_path}'!")
                time.sleep(1)
        else:
            if target == "leader":
                self.mgr.update_ports(leader_port=chosen.id)
            else:
                self.mgr.update_ports(follower_port=chosen.id)
            print_success(f"Assigned {target} arm to '{chosen.id}'!")
            time.sleep(1)

    # ========================================================================
    # Submenu: Cameras
    # ========================================================================

    def _menu_cameras(self) -> None:
        """Camera management submenu."""
        while True:
            profile = self.mgr.get_active_profile()
            cams = scan_cameras(active_cameras=profile.cameras)

            items = [
                MenuItem(
                    id="scan",
                    label="Scan & List Connected Cameras",
                    icon="🔍",
                    description=f"Discovered {len([c for c in cams if c.available])} functional camera(s).",
                ),
                MenuItem(
                    id="preview",
                    label="Preview Camera Snapshot (Terminal ASCII)",
                    icon="🖼️",
                    description="Capture live snapshot and render visual ASCII/ANSI preview in terminal.",
                ),
                MenuItem(
                    id="assign",
                    label="Assign Camera to Role (wrist, overhead, laptop)",
                    icon="🏷️",
                    description="Bind camera index to role in current profile.",
                ),
                MenuItem(
                    id="remove",
                    label="Remove Camera from Profile",
                    icon="🗑️",
                    description="Remove a camera configuration.",
                ),
                MenuItem(
                    id="wizard",
                    label="Guided Camera Wizard",
                    icon="🪄",
                    description="Step-by-step interactive camera setup dialog.",
                ),
                MenuItem(
                    id="back",
                    label="Back to Hardware Menu",
                    icon="↩️",
                    description="Return to hardware menu.",
                ),
            ]

            choice = run_menu(
                title="Camera Setup & Preview",
                subtitle="Configure camera video streams for recording and teleoperation:",
                items=items,
                active_profile=profile,
                breadcrumbs=["Home", "Hardware", "Cameras"],
            )

            if choice is None or choice.id == "back":
                break

            clear_terminal()

            if choice.id == "scan":
                display_cameras_table(cams)
                pause_return_to_menu()

            elif choice.id == "preview":
                available_cams = [c for c in cams if c.available]
                if not available_cams:
                    print_warning("No functional cameras detected.")
                    pause_return_to_menu()
                    continue

                cam_choices = [
                    MenuItem(
                        id=str(c.index),
                        label=f"Camera #{c.index} ({c.width}x{c.height})",
                        icon="📷",
                        description=c.v4l2_path or f"OpenCV Index {c.index}",
                    )
                    for c in available_cams
                ]
                cam_choices.append(MenuItem(id="cancel", label="Cancel", icon="↩️"))

                chosen_cam = run_menu(
                    title="Select Camera to Preview",
                    subtitle="Choose camera index to render snapshot preview:",
                    items=cam_choices,
                    active_profile=profile,
                    breadcrumbs=["Home", "Hardware", "Cameras", "Preview"],
                )
                if chosen_cam and chosen_cam.id != "cancel":
                    clear_terminal()
                    preview_txt = capture_snapshot_preview(int(chosen_cam.id))
                    if preview_txt:
                        console.print(f"\n[bold green]Live Snapshot for Camera #{chosen_cam.id}:[/bold green]\n")
                        console.print(preview_txt)
                    pause_return_to_menu()

            elif choice.id == "assign":
                cam_choices = [
                    MenuItem(id=str(c.index), label=f"Camera #{c.index}", icon="📷", description=f"Path: {c.v4l2_path or c.index}")
                    for c in cams
                ]
                cam_choices.append(MenuItem(id="cancel", label="Cancel", icon="↩️"))

                chosen_cam = run_menu(
                    title="Assign Camera Device",
                    subtitle="Select which camera hardware device to configure:",
                    items=cam_choices,
                    active_profile=profile,
                    breadcrumbs=["Home", "Hardware", "Cameras", "Assign"],
                )
                if chosen_cam and chosen_cam.id != "cancel":
                    role_choices = [
                        MenuItem(id="laptop", label="laptop", icon="💻", description="Front laptop / desk camera"),
                        MenuItem(id="wrist", label="wrist", icon="🦾", description="Camera mounted on follower arm wrist"),
                        MenuItem(id="overhead", label="overhead", icon="🔭", description="Top-down / overhead perspective"),
                        MenuItem(id="phone", label="phone", icon="📱", description="Mobile / secondary side angle"),
                        MenuItem(id="custom", label="Custom Role...", icon="✍️", description="Enter custom name"),
                    ]
                    chosen_role = run_menu(
                        title="Select Camera Role",
                        subtitle=f"Assign Camera #{chosen_cam.id} to which role?",
                        items=role_choices,
                        active_profile=profile,
                        breadcrumbs=["Home", "Hardware", "Cameras", "Assign Role"],
                    )
                    if chosen_role:
                        role_name = chosen_role.id
                        if role_name == "custom":
                            role_name = Prompt.ask("Enter custom role name")
                        self.mgr.update_camera(role_name, chosen_cam.id)
                        print_success(f"Assigned Camera #{chosen_cam.id} to role '{role_name}'!")
                        time.sleep(1)

            elif choice.id == "remove":
                if not profile.cameras:
                    print_info("No cameras configured in current profile.")
                    pause_return_to_menu()
                    continue

                cam_items = [
                    MenuItem(id=k, label=k, icon="📷", description=f"Index: {c.index_or_path}")
                    for k, c in profile.cameras.items()
                ]
                cam_items.append(MenuItem(id="cancel", label="Cancel", icon="↩️"))

                chosen_rem = run_menu(
                    title="Remove Camera",
                    subtitle="Select camera role to remove from profile:",
                    items=cam_items,
                    active_profile=profile,
                    breadcrumbs=["Home", "Hardware", "Cameras", "Remove"],
                )
                if chosen_rem and chosen_rem.id != "cancel":
                    self.mgr.remove_camera(chosen_rem.id)
                    print_success(f"Removed camera '{chosen_rem.id}' from profile!")
                    time.sleep(1)

            elif choice.id == "wizard":
                run_interactive_camera_wizard(self.mgr)
                pause_return_to_menu()

    # ========================================================================
    # Submenu: Profiles & Configuration
    # ========================================================================

    def _menu_profiles(self) -> None:
        """Profiles submenu."""
        while True:
            profile = self.mgr.get_active_profile()

            items = [
                MenuItem(
                    id="switch",
                    label="Switch Active Profile",
                    icon="🔄",
                    description=f"Currently active: {profile.name}. Choose from all saved profiles.",
                ),
                MenuItem(
                    id="create",
                    label="Create New Profile",
                    icon="➕",
                    description="Create a new profile for another robot setup or lab desk.",
                ),
                MenuItem(
                    id="edit",
                    label="Quick Setup Parameters",
                    icon="⚙️",
                    description=f"Edit robot type ({profile.robot_type}), default FPS ({profile.default_fps}), dataset repo, or notes.",
                ),
                MenuItem(
                    id="show",
                    label="View Profile Details",
                    icon="👁️",
                    description="Inspect active profile configuration summary.",
                ),
                MenuItem(
                    id="delete",
                    label="Delete Profile",
                    icon="🗑️",
                    description="Remove a profile from disk.",
                ),
                MenuItem(
                    id="back",
                    label="Back to Main Menu",
                    icon="↩️",
                    description="Return to previous menu.",
                ),
            ]

            choice = run_menu(
                title="Profiles & Configuration",
                subtitle="Manage hardware configurations and profiles:",
                items=items,
                active_profile=profile,
                breadcrumbs=["Home", "Profiles"],
            )

            if choice is None or choice.id == "back":
                break

            clear_terminal()

            if choice.id == "switch":
                profile_choices = [
                    MenuItem(
                        id=pname,
                        label=pname,
                        icon="🤖" if pname != profile.name else "⭐",
                        description=f"Type: {p.robot_type} | Leader: {p.leader_arm.port or 'None'} | Follower: {p.follower_arm.port or 'None'}",
                        badge="ACTIVE" if pname == profile.name else None,
                    )
                    for pname, p in self.mgr.config.profiles.items()
                ]
                profile_choices.append(MenuItem(id="cancel", label="Cancel", icon="↩️"))

                chosen_p = run_menu(
                    title="Switch Active Profile",
                    subtitle="Select profile to make active:",
                    items=profile_choices,
                    active_profile=profile,
                    breadcrumbs=["Home", "Profiles", "Switch"],
                )
                if chosen_p and chosen_p.id != "cancel":
                    self.mgr.set_active_profile(chosen_p.id)
                    print_success(f"Switched active profile to [bold green]{chosen_p.id}[/bold green]!")
                    time.sleep(1)

            elif choice.id == "create":
                console.print("\n[bold cyan]Create New Robot Profile[/bold cyan]\n")
                name = Prompt.ask("Profile name (e.g. so100-desk, koch-lab)")
                robot_type = Prompt.ask("Robot type", choices=SUPPORTED_ROBOTS, default="so100")
                notes = Prompt.ask("Notes / Description (optional)", default="")
                self.mgr.create_profile(name=name, robot_type=robot_type, notes=notes)
                if Confirm.ask(f"Set '{name}' as the active profile?", default=True):
                    self.mgr.set_active_profile(name)
                print_success(f"Created profile '{name}'!")
                time.sleep(1)

            elif choice.id == "edit":
                console.print(f"\n[bold cyan]Edit Parameters for Profile: [green]{profile.name}[/green][/bold cyan]\n")
                new_type = Prompt.ask("Robot type", choices=SUPPORTED_ROBOTS, default=profile.robot_type)
                new_teleop = Prompt.ask("Teleoperator type", default=profile.teleop_type)
                new_fps = int(Prompt.ask("Default recording/teleop FPS", default=str(profile.default_fps)))
                new_repo = Prompt.ask("Default dataset repo ID", default=profile.dataset_repo_id)
                new_notes = Prompt.ask("Notes", default=profile.notes)

                profile.robot_type = new_type
                profile.teleop_type = new_teleop
                profile.default_fps = new_fps
                profile.dataset_repo_id = new_repo
                profile.notes = new_notes
                self.mgr.save()
                print_success("Parameters updated successfully!")
                time.sleep(1)

            elif choice.id == "show":
                console.print(f"\n[bold cyan]Active Profile Summary: [green]{profile.name}[/green][/bold cyan]\n")
                console.print(f"  • Robot Type:    [bold]{profile.robot_type}[/bold]")
                console.print(f"  • Teleop Type:   [bold]{profile.teleop_type}[/bold]")
                console.print(f"  • Leader Port:   [bold cyan]{profile.leader_arm.port or 'Not Set'}[/bold cyan]")
                console.print(f"  • Follower Port: [bold cyan]{profile.follower_arm.port or 'Not Set'}[/bold cyan]")
                console.print(f"  • Dataset Repo:  [bold]{profile.dataset_repo_id}[/bold]")
                console.print(f"  • Default FPS:   [bold]{profile.default_fps}[/bold]")
                console.print(f"  • Cameras:       [bold]{len(profile.cameras)} configured[/bold]")
                pause_return_to_menu()

            elif choice.id == "delete":
                if len(self.mgr.config.profiles) <= 1:
                    print_error("Cannot delete the only remaining profile.")
                    pause_return_to_menu()
                    continue

                p_choices = [
                    MenuItem(id=pname, label=pname, icon="🗑️", description=f"Type: {p.robot_type}")
                    for pname in self.mgr.config.profiles
                ]
                p_choices.append(MenuItem(id="cancel", label="Cancel", icon="↩️"))

                del_choice = run_menu(
                    title="Delete Profile",
                    subtitle="Select profile to permanently remove:",
                    items=p_choices,
                    active_profile=profile,
                    breadcrumbs=["Home", "Profiles", "Delete"],
                )
                if del_choice and del_choice.id != "cancel":
                    if Confirm.ask(f"Are you sure you want to delete profile '{del_choice.id}'?", default=False):
                        self.mgr.delete_profile(del_choice.id)
                        print_success(f"Deleted profile '{del_choice.id}'.")
                        time.sleep(1)

    # ========================================================================
    # Submenu: Calibration Manager
    # ========================================================================

    def _menu_calibration(self) -> None:
        """Calibration submenu."""
        cal_mgr = CalibrationManager()

        while True:
            profile = self.mgr.get_active_profile()
            cal_files = cal_mgr.list_calibrations()

            items = [
                MenuItem(
                    id="list_inspect",
                    label="Browse & Inspect Calibrations",
                    icon="📋",
                    description=f"Discovered {len(cal_files)} calibration file(s). View joint homing offsets & travel ranges.",
                    badge=f"{len(cal_files)} files",
                ),
                MenuItem(
                    id="diff",
                    label="Compare / Diff Two Calibrations",
                    icon="⚖️",
                    description="Side-by-side comparison with joint offset and range difference highlights.",
                ),
                MenuItem(
                    id="backup",
                    label="Create Backup Archive",
                    icon="💾",
                    description="Save timestamped snapshot of all calibration files.",
                ),
                MenuItem(
                    id="restore",
                    label="Restore from Backup",
                    icon="♻️",
                    description="Restore calibration files from previous backup snapshot.",
                ),
                MenuItem(
                    id="export",
                    label="Export Calibration to File",
                    icon="📤",
                    description="Export JSON file to share or archive.",
                ),
                MenuItem(
                    id="import",
                    label="Import External Calibration",
                    icon="📥",
                    description="Import a calibration JSON file into LeRobot cache.",
                ),
                MenuItem(
                    id="back",
                    label="Back to Main Menu",
                    icon="↩️",
                    description="Return to previous menu.",
                ),
            ]

            choice = run_menu(
                title="Calibration Files Manager",
                subtitle="Inspect joint limits, homing offsets, and manage calibration backups:",
                items=items,
                active_profile=profile,
                breadcrumbs=["Home", "Calibration"],
            )

            if choice is None or choice.id == "back":
                break

            clear_terminal()

            if choice.id == "list_inspect":
                if not cal_files:
                    print_warning("No calibration files found in LeRobot cache.")
                    console.print("[dim]Run 'clirobot calibrate run' to generate calibration for your arm.[/dim]")
                    pause_return_to_menu()
                    continue

                file_choices = [
                    MenuItem(
                        id=f"{f.robot_type}/{f.robot_id}",
                        label=f"{f.robot_type} / {f.robot_id}",
                        icon="📐",
                        description=f"File: {f.path.name} | Modified: {f.modified_time.strftime('%Y-%m-%d %H:%M')}",
                    )
                    for f in cal_files
                ]
                file_choices.append(MenuItem(id="cancel", label="Cancel", icon="↩️"))

                chosen_cal = run_menu(
                    title="Select Calibration to Inspect",
                    subtitle="Choose calibration file to view joint registers:",
                    items=file_choices,
                    active_profile=profile,
                    breadcrumbs=["Home", "Calibration", "Inspect"],
                )
                if chosen_cal and chosen_cal.id != "cancel":
                    clear_terminal()
                    info = cal_mgr.get_calibration(chosen_cal.id)
                    if info:
                        inspect_calibration(info)
                    pause_return_to_menu()

            elif choice.id == "diff":
                if len(cal_files) < 2:
                    print_warning("Need at least two calibration files to compare.")
                    pause_return_to_menu()
                    continue

                file_choices = [
                    MenuItem(id=f"{f.robot_type}/{f.robot_id}", label=f"{f.robot_type} / {f.robot_id}", icon="📐")
                    for f in cal_files
                ]
                file_choices.append(MenuItem(id="cancel", label="Cancel", icon="↩️"))

                cal_a = run_menu("Select Calibration A", "Choose first file:", file_choices, active_profile=profile)
                if not cal_a or cal_a.id == "cancel":
                    continue

                cal_b = run_menu("Select Calibration B", "Choose second file to compare against A:", file_choices, active_profile=profile)
                if not cal_b or cal_b.id == "cancel":
                    continue

                clear_terminal()
                info_a = cal_mgr.get_calibration(cal_a.id)
                info_b = cal_mgr.get_calibration(cal_b.id)
                if info_a and info_b:
                    diff_calibrations(info_a, info_b)
                pause_return_to_menu()

            elif choice.id == "backup":
                backed_up = cal_mgr.backup()
                if backed_up:
                    print_success(f"Backed up {len(backed_up)} calibration file(s)!")
                else:
                    print_warning("No calibration files to backup.")
                pause_return_to_menu()

            elif choice.id == "restore":
                backups = cal_mgr.list_backups()
                if not backups:
                    print_warning("No backup archives found.")
                    pause_return_to_menu()
                    continue

                b_choices = [
                    MenuItem(id=name, label=name, icon="💾", description=f"{len(files)} files in archive")
                    for name, files in backups
                ]
                b_choices.append(MenuItem(id="cancel", label="Cancel", icon="↩️"))

                chosen_b = run_menu("Select Backup to Restore", "Choose backup archive:", b_choices, active_profile=profile)
                if chosen_b and chosen_b.id != "cancel":
                    count = cal_mgr.restore_backup(chosen_b.id)
                    print_success(f"Restored {count} file(s) from '{chosen_b.id}'!")
                    pause_return_to_menu()

            elif choice.id == "export":
                if not cal_files:
                    print_warning("No calibration files available to export.")
                    pause_return_to_menu()
                    continue
                ident = Prompt.ask("Enter calibration ID (e.g. so100/main)")
                dest = Prompt.ask("Enter destination path (e.g. ./calib.json)")
                try:
                    out = cal_mgr.export_calibration(ident, Path(dest))
                    print_success(f"Exported to {out}!")
                except Exception as e:
                    print_error(f"Export error: {e}")
                pause_return_to_menu()

            elif choice.id == "import":
                src = Prompt.ask("Enter path to external JSON file")
                rtype = Prompt.ask("Robot type", choices=SUPPORTED_ROBOTS, default="so100")
                rid = Prompt.ask("Arm ID", default="imported")
                try:
                    out = cal_mgr.import_calibration(Path(src), robot_type=rtype, robot_id=rid)
                    print_success(f"Imported calibration into {out}!")
                except Exception as e:
                    print_error(f"Import error: {e}")
                pause_return_to_menu()

    # ========================================================================
    # Submenu: Datasets & Visualization
    # ========================================================================

    def _menu_datasets(self) -> None:
        """Datasets submenu."""
        while True:
            profile = self.mgr.get_active_profile()

            items = [
                MenuItem(
                    id="viz",
                    label="Launch Dataset Visualizer (Rerun)",
                    icon="📊",
                    description=f"Launch visualizer for repo '{profile.dataset_repo_id}'.",
                ),
                MenuItem(
                    id="edit",
                    label="Edit / Trim Dataset Episodes",
                    icon="✂️",
                    description="Run lerobot-edit-dataset to filter or trim episodes.",
                ),
                MenuItem(
                    id="annotate",
                    label="Annotate Episodes with Language",
                    icon="🏷️",
                    description="Interactive tool to add natural language instructions to episodes.",
                ),
                MenuItem(
                    id="prune",
                    label="Prune Dataset (Drop Depth / Slices)",
                    icon="🧹",
                    description="Strip depth streams or slice state/action DoFs to prepare clean training data.",
                ),
                MenuItem(
                    id="split",
                    label="Split Dataset by Annotations",
                    icon="🔪",
                    description="Divide episodes into subdatasets using visualizer subtask annotations.",
                ),
                MenuItem(
                    id="inspect_ann",
                    label="Inspect Dataset Annotations",
                    icon="🔍",
                    description="Summary report of subtasks, VQA, speech tags, and episode coverage.",
                ),
                MenuItem(
                    id="sidecar",
                    label="Build Fast-Streaming MP4 Sidecars",
                    icon="🎬",
                    description="Build MP4 video sidecars for instant video streaming playback.",
                ),
                MenuItem(
                    id="transform",
                    label="Visualize Image Transformations",
                    icon="🎨",
                    description="Run lerobot-imgtransform-viz to inspect image augmentations.",
                ),
                MenuItem(
                    id="back",
                    label="Back to Main Menu",
                    icon="↩️",
                    description="Return to previous menu.",
                ),
            ]

            choice = run_menu(
                title="Datasets & Visualization",
                subtitle="Explore, annotate, edit, prune, split, and build video sidecars for datasets:",
                items=items,
                active_profile=profile,
                breadcrumbs=["Home", "Datasets"],
            )

            if choice is None or choice.id == "back":
                break

            clear_terminal()

            if choice.id == "viz":
                repo = Prompt.ask("Dataset repo ID", default=profile.dataset_repo_id)
                self.runner.run("dataset-viz", [f"--repo-id={repo}"])
                pause_return_to_menu()

            elif choice.id == "prune":
                from clirobot.dataset.prune import prune_dataset, display_prune_result
                repo = Prompt.ask("Dataset path or HF repo ID", default=profile.dataset_repo_id)
                drop_d = Confirm.ask("Drop depth observation streams & videos?", default=True)
                drop_e = Confirm.ask("Slice state and action to 6 DoF (remove extra EE axes)?", default=True)
                out_p = Prompt.ask("Destination directory (leave blank for in-place / temp)", default="")
                try:
                    res = prune_dataset(
                        dataset_path=repo,
                        output_path=out_p if out_p.strip() else None,
                        drop_depth=drop_d,
                        drop_ee=drop_e,
                    )
                    display_prune_result(res)
                except Exception as e:
                    print_error(f"Prune error: {e}")
                pause_return_to_menu()

            elif choice.id == "split":
                from clirobot.dataset.split import split_dataset, display_split_results
                repo = Prompt.ask("Dataset path or HF repo ID", default=profile.dataset_repo_id)
                strategy = Prompt.ask("Annotation split strategy", choices=["subtask", "task_aug", "plan", "vqa", "speech"], default="subtask")
                out_d = Prompt.ask("Output directory for subdatasets", default="./subdatasets")
                drop_d = Confirm.ask("Drop depth streams during split?", default=False)
                drop_e = Confirm.ask("Slice state/actions to 6 DoF during split?", default=False)
                try:
                    results = split_dataset(
                        dataset_path=repo,
                        output_dir=out_d,
                        annotation_type=strategy,
                        drop_depth=drop_d,
                        drop_ee=drop_e,
                        overwrite=True,
                    )
                    display_split_results(results)
                except Exception as e:
                    print_error(f"Split error: {e}")
                pause_return_to_menu()

            elif choice.id == "inspect_ann":
                from clirobot.dataset.annotations import inspect_annotations, display_annotation_summary
                repo = Prompt.ask("Dataset path or HF repo ID", default=profile.dataset_repo_id)
                try:
                    summary = inspect_annotations(Path(repo))
                    display_annotation_summary(summary)
                except Exception as e:
                    print_error(f"Annotation inspection error: {e}")
                pause_return_to_menu()

            elif choice.id == "edit":
                repo = Prompt.ask("Dataset repo ID", default=profile.dataset_repo_id)
                self.runner.run("edit-dataset", [f"--repo-id={repo}"])
                pause_return_to_menu()

            elif choice.id == "annotate":
                repo = Prompt.ask("Dataset repo ID", default=profile.dataset_repo_id)
                self.runner.run("annotate", [f"--repo-id={repo}"])
                pause_return_to_menu()

            elif choice.id == "sidecar":
                repo = Prompt.ask("Dataset repo ID", default=profile.dataset_repo_id)
                self.runner.run("build-mp4-sidecar", [f"--repo-id={repo}"])
                pause_return_to_menu()

            elif choice.id == "transform":
                repo = Prompt.ask("Dataset repo ID", default=profile.dataset_repo_id)
                self.runner.run("imgtransform-viz", [f"--repo-id={repo}"])
                pause_return_to_menu()
