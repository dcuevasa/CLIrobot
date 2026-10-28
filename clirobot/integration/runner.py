"""Command runner and execution dispatcher for LeRobot scripts and binaries."""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Any, Sequence
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from clirobot.constants import LEROBOT_BINARIES_MAP, LEROBOT_COMMANDS_MAP
from clirobot.ui.console import console, print_info, print_warning, print_error, print_success, make_card
from clirobot.config.manager import ConfigManager
from clirobot.plugins.base import ExecutionPlan, PluginContext


class CommandRunner:
    """Dispatches and streams execution of LeRobot commands with profile integration and plugin middlewares."""

    def __init__(self, config_manager: ConfigManager | None = None):
        self.config_manager = config_manager or ConfigManager()

    def resolve_executable(self, command_key: str) -> tuple[str, list[str]]:
        """Resolve whether to execute a standalone binary or python -m script.
        
        Returns:
            (executable, base_args_list)
        """
        binary_name = LEROBOT_BINARIES_MAP.get(command_key, f"lerobot-{command_key}")
        script_module = LEROBOT_COMMANDS_MAP.get(command_key)

        # 1. Check custom configured path
        custom_path = self.config_manager.config.lerobot_path
        if custom_path:
            p = Path(custom_path)
            if p.is_dir():
                bin_in_dir = p / "bin" / binary_name
                if bin_in_dir.exists() and os.access(bin_in_dir, os.X_OK):
                    return str(bin_in_dir), []
            elif p.is_file() and os.access(p, os.X_OK):
                # Custom python interpreter
                if script_module:
                    return str(p), ["-m", script_module]

        # 2. Check system PATH for binary
        bin_path = shutil.which(binary_name)
        if bin_path:
            return bin_path, []

        # 3. Fallback to active Python interpreter with module
        if script_module:
            return sys.executable, ["-m", script_module]

        # 4. Fallback default
        return binary_name, []

    def run(
        self,
        command_key: str,
        args: list[str],
        dry_run: bool = False,
        capture_output: bool = False,
        runtime_options: dict[str, Any] | None = None,
    ) -> int:
        """Execute the command through plugin middlewares with streaming output or dry-run inspection."""
        plan = ExecutionPlan(command_key=command_key, args=list(args))

        # Apply runtime middlewares
        try:
            from clirobot.plugins.manager import PluginManager

            pm = PluginManager(self.config_manager)
            middlewares = pm.get_middlewares_for_command(command_key)
            if middlewares:
                ctx = PluginContext(self.config_manager, self, console)
                for mw in middlewares:
                    plan = mw.mutate_execution_plan(plan, ctx, runtime_options=runtime_options)
        except Exception as e:
            # Fall back to unmutated execution if plugins encounter an issue
            pass

        return self.run_plan(plan, dry_run=dry_run, capture_output=capture_output)

    def run_plan(
        self,
        plan: ExecutionPlan,
        dry_run: bool = False,
        capture_output: bool = False,
    ) -> int:
        """Execute a concrete ExecutionPlan."""
        if plan.executable_override:
            exe, base_args = plan.executable_override
        else:
            exe, base_args = self.resolve_executable(plan.command_key)

        full_command = [exe] + base_args + plan.args

        # Display command launch panel
        cmd_str = " \\\n  ".join([f'"{c}"' if " " in c or "{" in c else c for c in full_command])

        if dry_run:
            console.print(
                Panel(
                    Syntax(cmd_str, "bash", theme="monokai", word_wrap=True),
                    title=f"[bold yellow]⚡ DRY RUN: {plan.command_key}[/bold yellow]",
                    subtitle="[dim]Copy and execute directly or run without --dry-run[/dim]",
                    border_style="yellow",
                    padding=(1, 2),
                )
            )
            return 0

        console.print(
            Panel(
                Syntax(cmd_str, "bash", theme="monokai", word_wrap=True),
                title=f"[bold green]▶ Launching LeRobot: {plan.command_key}[/bold green]",
                border_style="bright_blue",
                padding=(0, 2),
            )
        )

        env = os.environ.copy()
        if plan.env_overrides:
            env.update(plan.env_overrides)

        try:
            process = subprocess.Popen(
                full_command,
                stdout=None if not capture_output else subprocess.PIPE,
                stderr=None if not capture_output else subprocess.PIPE,
                text=True,
                env=env,
            )
            process.wait()
            return process.returncode
        except KeyboardInterrupt:
            console.print("\n[yellow]Process interrupted by user.[/yellow]")
            return 130
        except FileNotFoundError:
            print_error(
                f"Executable '{exe}' not found.\n"
                f"Ensure Hugging Face LeRobot is installed: [bold cyan]pip install lerobot[/bold cyan] "
                f"or set path via [bold cyan]clirobot config set lerobot_path /path/to/env[/bold cyan]"
            )
            return 127
        except Exception as e:
            print_error(f"Failed to execute command: {e}")
            return 1
