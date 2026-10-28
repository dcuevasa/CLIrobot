"""Base contracts, dataclasses, and interfaces for the CLIrobot plugin ecosystem."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, TYPE_CHECKING
import typer
from rich.console import Console

if TYPE_CHECKING:
    from clirobot.config.manager import ConfigManager
    from clirobot.config.schema import RobotProfile
    from clirobot.integration.runner import CommandRunner
    from clirobot.doctor.checker import CheckItem
    from clirobot.tui.menu import MenuItem


@dataclass
class PluginMetadata:
    """Declarative identity and capabilities of a CLIrobot plugin."""

    id: str
    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    category: Literal[
        "dataset", "vision", "control", "visualization", "hardware", "general"
    ] = "general"
    root_path: Optional[Path] = None
    requires_binaries: list[str] = field(default_factory=list)
    requires_packages: list[str] = field(default_factory=list)


@dataclass
class PluginContext:
    """Runtime context passed to every plugin action."""

    config_manager: "ConfigManager"
    runner: "CommandRunner"
    console: Console

    @property
    def active_profile(self) -> "RobotProfile":
        return self.config_manager.get_active_profile()

    def get_plugin_config(
        self, plugin_id: str, default: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Retrieve per-profile configuration namespace for this plugin."""
        return self.active_profile.plugin_configs.get(plugin_id, default or {})

    def save_plugin_config(self, plugin_id: str, data: dict[str, Any]) -> None:
        """Persist per-profile configuration namespace for this plugin."""
        self.active_profile.plugin_configs[plugin_id] = data
        self.config_manager.save()


@dataclass
class TUIMenuContribution:
    """Represents a menu item injected into the TUI by a plugin."""

    target_menu: Literal[
        "main", "control", "datasets", "hardware", "calibration", "plugins"
    ]
    item: "MenuItem"
    handler: Callable[[PluginContext], None]
    order: int = 100


class BasePlugin:
    """Base class that all CLIrobot plugins inherit from."""

    metadata: PluginMetadata

    def is_available(self) -> tuple[bool, str]:
        """Check whether the plugin's runtime dependencies are satisfied.

        Returns:
            (available: bool, status_reason: str)
        """
        return True, "Ready"

    def register_cli(
        self, root_app: typer.Typer, sub_apps: dict[str, typer.Typer]
    ) -> None:
        """Attach Typer commands to root_app or inject into existing sub_apps."""
        pass

    def get_tui_contributions(self, ctx: PluginContext) -> list[TUIMenuContribution]:
        """Return menu items to inject into TUI menus."""
        return []

    def run_doctor_checks(self, ctx: PluginContext) -> list["CheckItem"]:
        """Return plugin-specific diagnostic checks for `clirobot doctor`."""
        return []

    def get_default_profile_config(self) -> dict[str, Any]:
        """Default settings stored under profile.plugin_configs[self.metadata.id]."""
        return {}


# ==============================================================================
# Capability Mixin: DatasetTransformPlugin
# ==============================================================================


@dataclass
class DatasetTransformSpec:
    """Metadata and parameter schema for a composable dataset manipulation step."""

    id: str
    name: str
    description: str
    icon: str = "🛠️"
    supports_in_place: bool = False
    supports_dry_run: bool = True
    supports_hub_push: bool = True


@dataclass
class DatasetTransformResult:
    """Standardized output of any dataset manipulation tool."""

    transform_id: str
    success: bool
    input_repo_or_path: str
    output_path: Optional[str] = None
    output_repo_id: Optional[str] = None
    episodes_processed: int = 0
    frames_processed: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class DatasetTransformPlugin(BasePlugin):
    """Contract for plugins that manipulate, transform, or analyze LeRobot datasets."""

    def get_transforms(self) -> list[DatasetTransformSpec]:
        """Return specifications for transforms provided by this plugin."""
        return []

    def execute_transform(
        self,
        transform_id: str,
        ctx: PluginContext,
        input_repo: str,
        output_dir: Optional[str] = None,
        output_repo: Optional[str] = None,
        push_to_hub: bool = False,
        dry_run: bool = False,
        **kwargs: Any,
    ) -> DatasetTransformResult:
        """Execute the dataset transformation."""
        raise NotImplementedError

    def run_interactive_wizard(self, transform_id: str, ctx: PluginContext) -> None:
        """Interactive Rich prompt/menu flow when invoked from the TUI Datasets menu."""
        pass


# ==============================================================================
# Capability Mixin: RuntimeMiddlewarePlugin
# ==============================================================================


@dataclass
class ExecutionPlan:
    """Represents the command key and argument list before CommandRunner executes it."""

    command_key: str
    executable_override: Optional[tuple[str, list[str]]] = None
    args: list[str] = field(default_factory=list)
    env_overrides: dict[str, str] = field(default_factory=dict)


class RuntimeMiddlewarePlugin(BasePlugin):
    """Contract for plugins that intercept or augment teleop, record, or eval execution."""

    def applies_to_commands(self) -> list[str]:
        """List of command keys this middleware can augment (e.g. ['record', 'teleoperate', 'eval'])."""
        return []

    def mutate_execution_plan(
        self,
        plan: ExecutionPlan,
        ctx: PluginContext,
        runtime_options: Optional[dict[str, Any]] = None,
    ) -> ExecutionPlan:
        """Modify CLI arguments, environment variables, or swap the target binary/module."""
        return plan


# ==============================================================================
# Capability Mixin: ServicePlugin
# ==============================================================================


@dataclass
class ServiceStatus:
    running: bool
    endpoints: dict[str, str] = field(default_factory=dict)
    pids: list[int] = field(default_factory=list)
    detail: str = ""


class ServicePlugin(BasePlugin):
    """Contract for plugins that manage background/foreground servers or web UIs."""

    def start_service(
        self, ctx: PluginContext, foreground: bool = True, **kwargs: Any
    ) -> int:
        """Start the service process."""
        raise NotImplementedError

    def stop_service(self, ctx: PluginContext) -> bool:
        """Stop running service process(es)."""
        raise NotImplementedError

    def get_service_status(self, ctx: PluginContext) -> ServiceStatus:
        """Query if the service is currently running."""
        raise NotImplementedError
