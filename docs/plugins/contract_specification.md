# Plugin Contract Specification

This document provides the exhaustive API reference and protocol specifications for writing CLIrobot plugins.

All base classes and data structures reside in `clirobot.plugins.base`.

---

## 1. Core Data Structures

### `PluginMetadata`
Declarative description of plugin identity and dependencies:

```python
@dataclass
class PluginMetadata:
    id: str                          # Unique identifier (e.g., 'vision-detector')
    name: str                        # Human-readable title
    version: str = "0.1.0"           # Semantic version
    description: str = ""            # Brief summary
    author: str = ""                 # Author or organization
    category: Literal[               # Functional category
        "dataset", "vision", "control", "visualization", "hardware", "general"
    ] = "general"
    root_path: Optional[Path] = None # Path to repo if discovered from workspace
    requires_binaries: list[str] = field(default_factory=list)
    requires_packages: list[str] = field(default_factory=list)
```

---

### `PluginContext`
Passed to every plugin action, granting safe access to the CLIrobot runtime:

```python
@dataclass
class PluginContext:
    config_manager: ConfigManager
    runner: CommandRunner
    console: Console

    @property
    def active_profile(self) -> RobotProfile:
        """Get the currently selected RobotProfile."""
        return self.config_manager.get_active_profile()

    def get_plugin_config(
        self, plugin_id: str, default: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Retrieve per-profile settings stored under profile.plugin_configs[plugin_id]."""
        return self.active_profile.plugin_configs.get(plugin_id, default or {})

    def save_plugin_config(self, plugin_id: str, data: dict[str, Any]) -> None:
        """Persist per-profile settings to disk."""
        self.active_profile.plugin_configs[plugin_id] = data
        self.config_manager.save()
```

---

### `TUIMenuContribution`
Defines an interactive menu item to inject into CLIrobot's arrow-key TUI:

```python
@dataclass
class TUIMenuContribution:
    target_menu: Literal[
        "main", "control", "datasets", "hardware", "calibration", "profiles", "plugins"
    ]
    item: MenuItem
    handler: Callable[[PluginContext], None]
    order: int = 100
```

---

## 2. Base Plugin Interface (`BasePlugin`)

All plugins must subclass `BasePlugin`:

```python
class BasePlugin:
    metadata: PluginMetadata

    def is_available(self) -> tuple[bool, str]:
        """Check whether runtime dependencies are satisfied.
        Returns:
            (available: bool, status_reason: str)
        """
        return True, "Ready"

    def register_cli(
        self, root_app: typer.Typer, sub_apps: dict[str, typer.Typer]
    ) -> None:
        """Mount new top-level Typer groups or inject subcommands into existing groups:
        sub_apps['dataset'], sub_apps['record'], sub_apps['teleop'],
        sub_apps['eval'], sub_apps['ports'], sub_apps['profile'], etc.
        """
        pass

    def get_tui_contributions(self, ctx: PluginContext) -> list[TUIMenuContribution]:
        """Return interactive menu items for the TUI."""
        return []

    def run_doctor_checks(self, ctx: PluginContext) -> list[CheckItem]:
        """Return diagnostic health checks for `clirobot doctor`."""
        return []

    def get_default_profile_config(self) -> dict[str, Any]:
        """Return default settings for profile.plugin_configs[self.metadata.id]."""
        return {}
```

---

## 3. Specialized Capability Interfaces

### `DatasetTransformPlugin`
Implemented by tools that perform operations on recorded LeRobot datasets (pruning, splitting, augmenting, filtering, format export):

```python
@dataclass
class DatasetTransformSpec:
    id: str                  # e.g., 'vision-augment'
    name: str                # e.g., 'YOLO Vision Augmentation'
    description: str
    icon: str = "🛠️"
    supports_in_place: bool = False
    supports_dry_run: bool = True
    supports_hub_push: bool = True

@dataclass
class DatasetTransformResult:
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
    def get_transforms(self) -> list[DatasetTransformSpec]:
        """List transformation tools provided by this plugin."""
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
        """Prompt user interactively when launched from TUI Datasets menu."""
        pass
```

---

### `RuntimeMiddlewarePlugin`
Implemented by tools that hook into `teleop`, `record`, or `eval` execution loops:

```python
@dataclass
class ExecutionPlan:
    command_key: str
    executable_override: Optional[tuple[str, list[str]]] = None
    args: list[str] = field(default_factory=list)
    env_overrides: dict[str, str] = field(default_factory=dict)

class RuntimeMiddlewarePlugin(BasePlugin):
    def applies_to_commands(self) -> list[str]:
        """Return list of command keys intercepted (e.g., ['record', 'teleoperate', 'eval'])."""
        return []

    def mutate_execution_plan(
        self,
        plan: ExecutionPlan,
        ctx: PluginContext,
        runtime_options: Optional[dict[str, Any]] = None,
    ) -> ExecutionPlan:
        """Modify args, env vars, or swap the executable before launch."""
        return plan
```

---

### `ServicePlugin`
Implemented by tools that manage persistent servers, daemons, or web applications:

```python
@dataclass
class ServiceStatus:
    running: bool
    endpoints: dict[str, str] = field(default_factory=dict)
    pids: list[int] = field(default_factory=list)
    detail: str = ""

class ServicePlugin(BasePlugin):
    def start_service(
        self, ctx: PluginContext, foreground: bool = True, **kwargs: Any
    ) -> int:
        raise NotImplementedError

    def stop_service(self, ctx: PluginContext) -> bool:
        raise NotImplementedError

    def get_service_status(self, ctx: PluginContext) -> ServiceStatus:
        raise NotImplementedError
```
