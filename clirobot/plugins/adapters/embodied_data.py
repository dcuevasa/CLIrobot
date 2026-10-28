"""Adapter plugin for FLAG-Embodied-data.

Integrates physical and simulation data collection workflows, manual episode state machines,
FK end-effector pose injection, RealSense depth toggles, and shell environment importing.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Optional
import typer
from rich.panel import Panel

from clirobot.plugins.base import (
    BasePlugin,
    ExecutionPlan,
    PluginContext,
    PluginMetadata,
    RuntimeMiddlewarePlugin,
    TUIMenuContribution,
)
from clirobot.doctor.checker import CheckItem
from clirobot.tui.menu import MenuItem
from clirobot.ui.console import console, print_error, print_info, print_success


class EmbodiedDataPlugin(RuntimeMiddlewarePlugin):
    """Adapter for FLAG-Embodied-data robotics capture workflows."""

    metadata = PluginMetadata(
        id="embodied-data",
        name="FLAG Embodied Data Workflows",
        version="0.1.0",
        description="Physical and MuJoCo simulation recording with manual episode controls, FK EE pose, and RealSense depth.",
        category="control",
        author="Ruben, David Cuevas, Manuel Mosquera",
    )

    def _resolve_repo(self) -> Optional[Path]:
        """Locate sibling FLAG-Embodied-data directory if present."""
        clirobot_dir = Path(__file__).resolve().parent.parent.parent.parent
        workspace_root = clirobot_dir.parent
        candidate = workspace_root / "FLAG-Embodied-data"
        if candidate.is_dir():
            return candidate
        return None

    def is_available(self) -> tuple[bool, str]:
        repo = self._resolve_repo()
        if repo and (repo / "lerobot_record_physical.py").is_file():
            return True, f"Found in workspace ({repo.name})"
        return False, "FLAG-Embodied-data folder not found"

    # ==========================================================================
    # Capability: RuntimeMiddlewarePlugin
    # ==========================================================================

    def applies_to_commands(self) -> list[str]:
        return ["record", "teleoperate", "teleop"]

    def mutate_execution_plan(
        self,
        plan: ExecutionPlan,
        ctx: PluginContext,
        runtime_options: Optional[dict[str, Any]] = None,
    ) -> ExecutionPlan:
        cfg = ctx.get_plugin_config("embodied-data", {})
        opts = runtime_options or {}

        enable_ee = opts.get("enable_ee_pose", cfg.get("enable_ee_pose", False))
        enable_depth = opts.get("enable_depth", cfg.get("enable_depth", False))
        reset_ep = opts.get("reset_every_episode", cfg.get("reset_every_episode", False))
        randomize_scene = opts.get("randomize_scene", cfg.get("randomize_scene", False))

        if enable_ee:
            plan.args.append("--robot.enable_ee_pose=true")
        if enable_depth:
            plan.args.append("--robot.enable_depth=true")
        if reset_ep:
            plan.args.append("--robot.reset_every_episode=true")
        if randomize_scene:
            plan.args.append("--robot.randomize_scene=true")

        return plan

    # ==========================================================================
    # CLI Commands
    # ==========================================================================

    def register_cli(self, root_app: typer.Typer, sub_apps: dict[str, typer.Typer]) -> None:
        embodied_app = typer.Typer(
            name="embodied",
            help="FLAG-Embodied-data capture workflows and utilities.",
            no_args_is_help=False,
        )

        @embodied_app.command("import-env")
        def import_env(
            script_path: Path = typer.Argument(..., help="Path to set_variables.sh"),
            profile_name: Optional[str] = typer.Option(None, "--name", "-n", help="Target profile name"),
        ):
            """Import robot ports, camera IDs, and toggles from a set_variables.sh script."""
            from clirobot.config.manager import ConfigManager

            mgr = ConfigManager()
            try:
                prof = mgr.import_env_script(script_path, profile_name=profile_name)
                print_success(f"Successfully imported profile '[bold green]{prof.name}[/bold green]' from {script_path}!")
            except Exception as e:
                print_error(f"Failed to import environment script: {e}")

        @embodied_app.command("reset-rerun")
        def reset_rerun():
            """Reset active Rerun visualizer sessions."""
            import subprocess
            try:
                subprocess.run(["rerun", "reset"], check=False)
                print_success("Rerun sessions reset successfully.")
            except Exception as e:
                print_error(f"Error resetting rerun: {e}")

        root_app.add_typer(embodied_app, name="embodied", help="FLAG-Embodied-data utilities")

        # Mount record physical and record sim into `clirobot record`
        if "record" in sub_apps:
            record_app = sub_apps["record"]

            @record_app.command("physical")
            def record_physical(
                repo_id: Optional[str] = typer.Option(None, "--repo-id", "-r", help="Dataset repo ID"),
                num_episodes: int = typer.Option(10, "--episodes", "-e", help="Number of episodes"),
                task: Optional[str] = typer.Option(None, "--task", "-t", help="Single task description"),
                push_to_hub: bool = typer.Option(False, "--push-to-hub", help="Push to Hugging Face Hub"),
                enable_ee: bool = typer.Option(False, "--enable-ee-pose", help="Compute FK end-effector pose"),
                enable_depth: bool = typer.Option(False, "--enable-depth", help="Capture RealSense depth"),
                dry_run: bool = typer.Option(False, "--dry-run", help="Dry run command"),
            ):
                """Record physical robot episodes with interactive keyboard controls."""
                from clirobot.config.manager import ConfigManager
                from clirobot.integration.runner import CommandRunner
                from clirobot.integration.args_builder import LeRobotArgsBuilder

                mgr = ConfigManager()
                prof = mgr.get_active_profile()
                runner = CommandRunner(mgr)

                args = LeRobotArgsBuilder.build_record_args(
                    prof,
                    repo_id=repo_id,
                    num_episodes=num_episodes,
                    single_task=task,
                    push_to_hub=push_to_hub,
                    display_data=True,
                )
                if enable_ee:
                    args.append("--robot.enable_ee_pose=true")
                if enable_depth:
                    args.append("--robot.enable_depth=true")

                repo = self._resolve_repo()
                script_path = (repo / "lerobot_record_physical.py") if repo else None
                if script_path and script_path.is_file():
                    plan = ExecutionPlan(
                        command_key="record-physical",
                        executable_override=(sys.executable, [str(script_path)]),
                        args=args,
                    )
                    runner.run_plan(plan, dry_run=dry_run)
                else:
                    runner.run("record", args, dry_run=dry_run)

            @record_app.command("sim")
            def record_sim(
                repo_id: Optional[str] = typer.Option(None, "--repo-id", "-r", help="Dataset repo ID"),
                num_episodes: int = typer.Option(10, "--episodes", "-e", help="Number of episodes"),
                task: Optional[str] = typer.Option(None, "--task", "-t", help="Single task description"),
                randomize_scene: bool = typer.Option(True, "--randomize-scene", help="Randomize MuJoCo scene objects"),
                reset_every_episode: bool = typer.Option(True, "--reset-every-episode", help="Reset scene each episode"),
                push_to_hub: bool = typer.Option(False, "--push-to-hub", help="Push to Hugging Face Hub"),
                dry_run: bool = typer.Option(False, "--dry-run", help="Dry run command"),
            ):
                """Record MuJoCo simulation episodes with manual episode loop."""
                from clirobot.config.manager import ConfigManager
                from clirobot.integration.runner import CommandRunner
                from clirobot.integration.args_builder import LeRobotArgsBuilder

                mgr = ConfigManager()
                prof = mgr.get_active_profile()
                runner = CommandRunner(mgr)

                args = LeRobotArgsBuilder.build_record_args(
                    prof,
                    repo_id=repo_id,
                    num_episodes=num_episodes,
                    single_task=task,
                    push_to_hub=push_to_hub,
                    display_data=True,
                )
                if randomize_scene:
                    args.append("--robot.randomize_scene=true")
                if reset_every_episode:
                    args.append("--robot.reset_every_episode=true")

                repo = self._resolve_repo()
                script_path = (repo / "lerobot_record_sim.py") if repo else None
                if script_path and script_path.is_file():
                    plan = ExecutionPlan(
                        command_key="record-sim",
                        executable_override=(sys.executable, [str(script_path)]),
                        args=args,
                    )
                    runner.run_plan(plan, dry_run=dry_run)
                else:
                    runner.run("record", args, dry_run=dry_run)

    # ==========================================================================
    # TUI Contributions
    # ==========================================================================

    def get_tui_contributions(self, ctx: PluginContext) -> list[TUIMenuContribution]:
        return [
            TUIMenuContribution(
                target_menu="control",
                item=MenuItem(
                    id="record_physical_flag",
                    label="Record Physical (FLAG Manual Loop)",
                    icon="🔴",
                    description="Record physical robot episodes with manual keyboard listener (Enter/Right/Left/Space/Esc).",
                ),
                handler=self._tui_record_physical,
                order=15,
            ),
            TUIMenuContribution(
                target_menu="control",
                item=MenuItem(
                    id="record_sim_flag",
                    label="Record MuJoCo Simulation",
                    icon="🌐",
                    description="Record simulation episodes with scene randomization and episode reset.",
                ),
                handler=self._tui_record_sim,
                order=16,
            ),
            TUIMenuContribution(
                target_menu="profiles",
                item=MenuItem(
                    id="import_set_variables",
                    label="Import Profile from set_variables.sh",
                    icon="📥",
                    description="Parse FLAG-Embodied-data/scripts/set_variables.sh into a CLIrobot profile.",
                ),
                handler=self._tui_import_env,
                order=30,
            ),
        ]

    def _tui_record_physical(self, ctx: PluginContext) -> None:
        from rich.prompt import Confirm, Prompt
        from clirobot.integration.args_builder import LeRobotArgsBuilder

        prof = ctx.active_profile
        episodes = int(Prompt.ask("Episodes to record", default="10"))
        task = Prompt.ask("Task instruction", default="")
        enable_ee = Confirm.ask("Compute & save FK end-effector pose?", default=False)
        enable_d = Confirm.ask("Capture RealSense depth?", default=False)

        args = LeRobotArgsBuilder.build_record_args(
            prof, num_episodes=episodes, single_task=task or None, display_data=True
        )
        if enable_ee:
            args.append("--robot.enable_ee_pose=true")
        if enable_d:
            args.append("--robot.enable_depth=true")

        repo = self._resolve_repo()
        script = (repo / "lerobot_record_physical.py") if repo else None
        if script and script.is_file():
            plan = ExecutionPlan(
                command_key="record-physical",
                executable_override=(sys.executable, [str(script)]),
                args=args,
            )
            ctx.runner.run_plan(plan)
        else:
            ctx.runner.run("record", args)

    def _tui_record_sim(self, ctx: PluginContext) -> None:
        from rich.prompt import Confirm, Prompt
        from clirobot.integration.args_builder import LeRobotArgsBuilder

        prof = ctx.active_profile
        episodes = int(Prompt.ask("Episodes to record", default="10"))
        task = Prompt.ask("Task instruction", default="")
        rand = Confirm.ask("Randomize MuJoCo scene objects each episode?", default=True)
        reset_ep = Confirm.ask("Reset robot and scene each episode?", default=True)

        args = LeRobotArgsBuilder.build_record_args(
            prof, num_episodes=episodes, single_task=task or None, display_data=True
        )
        if rand:
            args.append("--robot.randomize_scene=true")
        if reset_ep:
            args.append("--robot.reset_every_episode=true")

        repo = self._resolve_repo()
        script = (repo / "lerobot_record_sim.py") if repo else None
        if script and script.is_file():
            plan = ExecutionPlan(
                command_key="record-sim",
                executable_override=(sys.executable, [str(script)]),
                args=args,
            )
            ctx.runner.run_plan(plan)
        else:
            ctx.runner.run("record", args)

    def _tui_import_env(self, ctx: PluginContext) -> None:
        from rich.prompt import Prompt

        repo = self._resolve_repo()
        default_sh = str(repo / "scripts" / "set_variables.sh") if repo else "./set_variables.sh"
        path_str = Prompt.ask("Path to set_variables.sh", default=default_sh)
        try:
            prof = ctx.config_manager.import_env_script(path_str)
            print_success(f"Imported profile '{prof.name}' successfully!")
        except Exception as e:
            print_error(f"Import failed: {e}")

    # ==========================================================================
    # Doctor Checks
    # ==========================================================================

    def run_doctor_checks(self, ctx: PluginContext) -> list[CheckItem]:
        checks = []
        is_avail, reason = self.is_available()
        checks.append(
            CheckItem(
                category="Embodied Data",
                name="FLAG Workflows Folder",
                status="PASS" if is_avail else "WARN",
                detail=reason,
                recommendation="" if is_avail else "Clone FLAG-Embodied-data in workspace",
            )
        )

        # Check for companion robot packages
        for pkg_name in ["lerobot_robot_so101_mujoco", "lerobot_teleoperator_so101_ik"]:
            found = False
            try:
                __import__(pkg_name)
                found = True
            except ImportError:
                pass
            checks.append(
                CheckItem(
                    category="Embodied Data",
                    name=f"Companion: {pkg_name}",
                    status="PASS" if found else "WARN",
                    detail="Installed" if found else "Not found in active environment",
                    recommendation="" if found else f"Run: pip install -e {pkg_name}",
                )
            )

        return checks
