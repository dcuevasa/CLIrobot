"""CLIrobot plugin architecture package."""

from clirobot.plugins.base import (
    BasePlugin,
    DatasetTransformPlugin,
    DatasetTransformResult,
    DatasetTransformSpec,
    ExecutionPlan,
    PluginContext,
    PluginMetadata,
    RuntimeMiddlewarePlugin,
    ServicePlugin,
    ServiceStatus,
    TUIMenuContribution,
)

__all__ = [
    "BasePlugin",
    "DatasetTransformPlugin",
    "DatasetTransformResult",
    "DatasetTransformSpec",
    "ExecutionPlan",
    "PluginContext",
    "PluginMetadata",
    "RuntimeMiddlewarePlugin",
    "ServicePlugin",
    "ServiceStatus",
    "TUIMenuContribution",
]
