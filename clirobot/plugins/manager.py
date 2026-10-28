"""PluginManager: Discovers, initializes, and coordinates CLIrobot plugins."""

from __future__ import annotations

import importlib
import importlib.metadata
import inspect
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
from clirobot.config.manager import ConfigManager
from clirobot.plugins.base import (
    BasePlugin,
    DatasetTransformPlugin,
    DatasetTransformSpec,
    ExecutionPlan,
    PluginContext,
    PluginMetadata,
    RuntimeMiddlewarePlugin,
    ServicePlugin,
    TUIMenuContribution,
)
from clirobot.ui.console import console

logger = logging.getLogger("clirobot.plugins.manager")


class PluginManager:
    """Central registry and lifecycle manager for all CLIrobot plugins."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config_manager = config_manager or ConfigManager()
        self._plugins: dict[str, BasePlugin] = {}
        self._discovered: bool = False

    def discover_plugins(self, force_reload: bool = False) -> dict[str, BasePlugin]:
        """Discover and load plugins from built-ins, entry points, and workspace paths."""
        if self._discovered and not force_reload:
            return self._plugins

        self._plugins.clear()

        # 1. Discover built-in adapters
        self._load_builtin_adapters()

        # 2. Discover via Python package entry_points (group="clirobot.plugins")
        self._load_entry_point_plugins()

        # 3. Discover workspace sibling repositories
        self._load_workspace_plugins()

        # 4. Discover custom search paths
        self._load_custom_path_plugins()

        self._discovered = True
        return self._plugins

    def _load_builtin_adapters(self) -> None:
        """Load internal built-in adapters."""
        builtin_names = [
            "clirobot.plugins.adapters.core_dataset",
            "clirobot.plugins.adapters.embodied_data",
            "clirobot.plugins.adapters.vision_detector",
            "clirobot.plugins.adapters.dataset_visualizer",
        ]
        for mod_name in builtin_names:
            try:
                mod = importlib.import_module(mod_name)
                self._register_plugins_from_module(mod)
            except ImportError as e:
                logger.debug(f"Could not load built-in adapter '{mod_name}': {e}")
            except Exception as e:
                logger.warning(f"Error loading built-in adapter '{mod_name}': {e}")

    def _load_entry_point_plugins(self) -> None:
        """Load plugins registered via pyproject.toml entry-points."""
        try:
            entry_points = importlib.metadata.entry_points(group="clirobot.plugins")
            for ep in entry_points:
                try:
                    plugin_cls = ep.load()
                    if inspect.isclass(plugin_cls) and issubclass(plugin_cls, BasePlugin):
                        instance = plugin_cls()
                        self._plugins[instance.metadata.id] = instance
                except Exception as e:
                    logger.warning(f"Failed to load entry-point plugin '{ep.name}': {e}")
        except Exception as e:
            logger.debug(f"Error checking entry points: {e}")

    def _load_workspace_plugins(self) -> None:
        """Auto-detect workspace sibling tools if present in thesis/lerobot."""
        import sys

        # Detect workspace root relative to CLIrobot location
        clirobot_dir = Path(__file__).resolve().parent.parent.parent
        workspace_root = clirobot_dir.parent

        known_siblings = [
            ("lerobot-vision-detector", "lerobot_vision_detector.clirobot_plugin"),
            ("FLAG-Embodied-data", "flag_embodied_data_plugin"),
            ("lerobot-dataset-visualizer", "lerobot_dataset_visualizer_plugin"),
        ]

        for folder_name, mod_target in known_siblings:
            sibling_dir = workspace_root / folder_name
            if sibling_dir.is_dir():
                if str(sibling_dir) not in sys.path:
                    sys.path.insert(0, str(sibling_dir))
                try:
                    mod = importlib.import_module(mod_target)
                    self._register_plugins_from_module(mod)
                except Exception:
                    # Will fall back to built-in bridge adapter
                    pass

    def _load_custom_path_plugins(self) -> None:
        """Scan paths configured in plugin_search_paths."""
        import sys

        for search_path_str in self.config_manager.config.plugin_search_paths:
            path = Path(search_path_str)
            if not path.is_dir():
                continue
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
            # Check for clirobot_plugin.py or plugin manifest
            plugin_file = path / "clirobot_plugin.py"
            if plugin_file.is_file():
                try:
                    mod_name = f"external_plugin_{path.name.replace('-', '_')}"
                    spec = importlib.util.spec_from_file_location(mod_name, plugin_file)
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        self._register_plugins_from_module(mod)
                except Exception as e:
                    logger.warning(f"Failed to load external plugin at {plugin_file}: {e}")

    def _register_plugins_from_module(self, mod: Any) -> None:
        """Find and instantiate all BasePlugin classes inside a module."""
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if (
                inspect.isclass(attr)
                and issubclass(attr, BasePlugin)
                and attr is not BasePlugin
                and attr not in (DatasetTransformPlugin, RuntimeMiddlewarePlugin, ServicePlugin)
            ):
                try:
                    instance = attr()
                    if hasattr(instance, "metadata") and instance.metadata and instance.metadata.id:
                        self._plugins[instance.metadata.id] = instance
                except Exception as e:
                    logger.warning(f"Error instantiating plugin '{attr_name}': {e}")

    # ==========================================================================
    # Query & Access Methods
    # ==========================================================================

    def get_plugin(self, plugin_id: str) -> Optional[BasePlugin]:
        """Get a plugin by ID if discovered."""
        self.discover_plugins()
        return self._plugins.get(plugin_id)

    def list_plugins(self, enabled_only: bool = False) -> list[BasePlugin]:
        """Return list of discovered plugins, optionally filtered by enabled status."""
        self.discover_plugins()
        plugins = list(self._plugins.values())
        if enabled_only:
            return [p for p in plugins if self.config_manager.is_plugin_enabled(p.metadata.id)]
        return plugins

    def get_dataset_transforms(self) -> dict[str, tuple[DatasetTransformPlugin, DatasetTransformSpec]]:
        """Return map of transform_id -> (plugin, spec) across all enabled plugins."""
        transforms: dict[str, tuple[DatasetTransformPlugin, DatasetTransformSpec]] = {}
        for plugin in self.list_plugins(enabled_only=True):
            if isinstance(plugin, DatasetTransformPlugin):
                for spec in plugin.get_transforms():
                    transforms[spec.id] = (plugin, spec)
        return transforms

    def get_middlewares_for_command(self, command_key: str) -> list[RuntimeMiddlewarePlugin]:
        """Return list of enabled RuntimeMiddlewarePlugins that apply to command_key."""
        middlewares: list[RuntimeMiddlewarePlugin] = []
        for plugin in self.list_plugins(enabled_only=True):
            if isinstance(plugin, RuntimeMiddlewarePlugin):
                if command_key in plugin.applies_to_commands() or "*" in plugin.applies_to_commands():
                    middlewares.append(plugin)
        return middlewares

    def get_services(self) -> list[ServicePlugin]:
        """Return list of all ServicePlugins among enabled plugins."""
        return [
            p for p in self.list_plugins(enabled_only=True)
            if isinstance(p, ServicePlugin)
        ]

    def get_tui_contributions(self, ctx: PluginContext) -> list[TUIMenuContribution]:
        """Collect all TUI menu contributions across enabled plugins sorted by order."""
        contributions: list[TUIMenuContribution] = []
        for plugin in self.list_plugins(enabled_only=True):
            try:
                contribs = plugin.get_tui_contributions(ctx)
                contributions.extend(contribs)
            except Exception as e:
                logger.warning(f"Error collecting TUI items for '{plugin.metadata.id}': {e}")
        return sorted(contributions, key=lambda c: c.order)

    def run_doctor_checks(self, ctx: PluginContext) -> list[Any]:
        """Run all doctor checks across discovered plugins."""
        checks = []
        for plugin in self.list_plugins(enabled_only=True):
            try:
                p_checks = plugin.run_doctor_checks(ctx)
                checks.extend(p_checks)
            except Exception as e:
                logger.warning(f"Error running doctor check for '{plugin.metadata.id}': {e}")
        return checks
