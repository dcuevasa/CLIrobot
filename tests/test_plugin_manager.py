"""Unit tests for CLIrobot PluginManager and Plugin contracts."""

import pytest
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
    ServiceStatus,
    TUIMenuContribution,
)
from clirobot.plugins.manager import PluginManager
from clirobot.tui.menu import MenuItem
from clirobot.ui.console import console


class DummyTransformPlugin(DatasetTransformPlugin):
    metadata = PluginMetadata(
        id="dummy-transform",
        name="Dummy Transform Tool",
        category="dataset",
    )

    def get_transforms(self) -> list[DatasetTransformSpec]:
        return [
            DatasetTransformSpec(
                id="dummy-op",
                name="Dummy Operation",
                description="Testing dummy operation",
            )
        ]


class DummyMiddlewarePlugin(RuntimeMiddlewarePlugin):
    metadata = PluginMetadata(
        id="dummy-mw",
        name="Dummy Middleware",
        category="control",
    )

    def applies_to_commands(self) -> list[str]:
        return ["record"]

    def mutate_execution_plan(self, plan: ExecutionPlan, ctx: PluginContext, runtime_options=None) -> ExecutionPlan:
        plan.args.append("--dummy-injected")
        return plan


def test_plugin_discovery_and_querying(tmp_path):
    cfg_file = tmp_path / "config.json"
    mgr = ConfigManager(config_path=cfg_file)
    pm = PluginManager(mgr)

    plugins = pm.list_plugins()
    assert len(plugins) >= 4

    p_ids = [p.metadata.id for p in plugins]
    assert "core-dataset" in p_ids
    assert "vision-detector" in p_ids
    assert "embodied-data" in p_ids
    assert "dataset-visualizer" in p_ids


def test_plugin_enable_disable(tmp_path):
    cfg_file = tmp_path / "config.json"
    mgr = ConfigManager(config_path=cfg_file)
    pm = PluginManager(mgr)

    assert mgr.is_plugin_enabled("vision-detector") is True

    mgr.disable_plugin("vision-detector")
    assert mgr.is_plugin_enabled("vision-detector") is False

    enabled_plugins = [p.metadata.id for p in pm.list_plugins(enabled_only=True)]
    assert "vision-detector" not in enabled_plugins

    mgr.enable_plugin("vision-detector")
    assert mgr.is_plugin_enabled("vision-detector") is True


def test_plugin_transforms_discovery(tmp_path):
    cfg_file = tmp_path / "config.json"
    mgr = ConfigManager(config_path=cfg_file)
    pm = PluginManager(mgr)

    transforms = pm.get_dataset_transforms()
    assert "prune" in transforms
    assert "split" in transforms
    assert "vision-augment" in transforms
    assert "export-v3-language" in transforms


def test_plugin_middlewares_discovery(tmp_path):
    cfg_file = tmp_path / "config.json"
    mgr = ConfigManager(config_path=cfg_file)
    pm = PluginManager(mgr)

    record_mws = pm.get_middlewares_for_command("record")
    mw_ids = [m.metadata.id for m in record_mws]
    assert "vision-detector" in mw_ids
    assert "embodied-data" in mw_ids

    # Teleoperate
    teleop_mws = pm.get_middlewares_for_command("teleoperate")
    t_ids = [m.metadata.id for m in teleop_mws]
    assert "vision-detector" in t_ids


def test_plugin_tui_contributions(tmp_path):
    cfg_file = tmp_path / "config.json"
    mgr = ConfigManager(config_path=cfg_file)
    pm = PluginManager(mgr)
    ctx = PluginContext(mgr, None, console)

    contribs = pm.get_tui_contributions(ctx)
    assert len(contribs) >= 4
    menus = {c.target_menu for c in contribs}
    assert "datasets" in menus
    assert "control" in menus
