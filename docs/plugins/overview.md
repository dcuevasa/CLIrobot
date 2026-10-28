# CLIrobot Plugin Architecture: Overview

## 1. Why a Plugin System?

Standard robotics workflows involve diverse, evolving tools:
* Vision detection models (YOLO, OWLv2, Grounding DINO)
* Simulation environments (MuJoCo, Isaac Sim)
* Web visualizers and 3D URDF playback tools
* Specialized data cleaning, temporal splitting, and language annotation backends

Embedding every tool directly into `CLIrobot` would result in a massive, fragile dependency tree (requiring PyTorch, CUDA, Ultralytics, MuJoCo, FastAPI, and Node/Bun simultaneously).

The **CLIrobot Plugin System** solves this by turning `CLIrobot` into an **extensible control hub**:
1. **Lightweight Core**: Core `CLIrobot` only depends on standard CLI libraries (`typer`, `rich`, `pyserial`, `pandas`, `pyarrow`, `huggingface_hub`).
2. **Zero Hard Dependencies**: Specialized dependencies remain isolated in their respective plugin packages or workspace repositories and are loaded lazily.
3. **Multi-Surface Integration**: A single plugin can contribute to:
   * **CLI Commands** (new top-level groups or subcommands under `clirobot dataset`, `clirobot record`, etc.)
   * **Interactive TUI Menus** (injecting items into `Control`, `Datasets`, `Hardware`, `Profiles`, or `Plugins`)
   * **Runtime Middleware** (intercepting `teleop`, `record`, or `eval` execution to inject CLI flags or swap binaries)
   * **Composable Dataset Transforms** (registering data tools into the `DatasetPipelineEngine`)
   * **Managed Background Services** (controlling web apps and daemon processes)
   * **System Doctor Checks** (contributing diagnostics to `clirobot doctor`)

---

## 2. High-Level Architecture

```text
                               +-----------------------------+
                               |     CLIrobot Core (clr)     |
                               +--------------+--------------+
                                              |
                     +------------------------+------------------------+
                     |                        |                        |
                     v                        v                        v
        +-------------------------+  +------------------+  +-----------------------+
        | Typer CLI Router        |  | Interactive TUI  |  | System Doctor         |
        | (Dynamic Sub-Apps)      |  | (Dynamic Menus)  |  | (Plugin Diagnostics)  |
        +------------+------------+  +--------+---------+  +-----------+-----------+
                     |                        |                        |
                     +------------------------+------------------------+
                                              |
                                              v
                              +-------------------------------+
                              |         PluginManager         |
                              +---------------+---------------+
                                              |
           +----------------------------------+----------------------------------+
           |                                  |                                  |
           v                                  v                                  v
+-----------------------+          +-----------------------+          +-----------------------+
|  Built-in Adapters    |          | Python Entry Points   |          | Workspace Discovery   |
| (clirobot.plugins.*)  |          | (pyproject.toml)      |          | (Sibling directories) |
+-----------------------+          +-----------------------+          +-----------------------+
```

---

## 3. The 3 Discovery Mechanisms

`PluginManager` scans for available plugins in three ways:

### 1. Built-in Core Adapters
Located in `clirobot.plugins.adapters.*`. Provides default adapters for `core-dataset`, `vision-detector`, `embodied-data`, and `dataset-visualizer`.

### 2. Standard Python Package Entry Points
Any installed pip package can register as a CLIrobot plugin by adding an entry point in its `pyproject.toml`:
```toml
[project.entry-points."clirobot.plugins"]
my-custom-plugin = "my_package.clirobot_plugin:MyCustomPlugin"
```
When `CLIrobot` starts, it automatically queries `importlib.metadata.entry_points(group="clirobot.plugins")` and mounts the plugin.

### 3. Workspace Sibling Repositories & Custom Search Paths
For multi-repo monorepos or development workspaces, `PluginManager` automatically detects sibling folders in the parent directory (e.g. `../lerobot-vision-detector`, `../FLAG-Embodied-data`, `../lerobot-dataset-visualizer`).

Users can also manually register any local directory:
```bash
clirobot plugin add /path/to/my-robot-tools
```

---

## 4. Capability Mixins

Plugins inherit from `BasePlugin` and implement one or more specialized capability interfaces:

| Capability Interface | Purpose | Examples |
| :--- | :--- | :--- |
| **`DatasetTransformPlugin`** | Exposes offline dataset operations with `--dry-run`, `--push-to-hub`, and pipeline chaining. | `prune`, `split`, `vision-augment`, `export-v3-language` |
| **`RuntimeMiddlewarePlugin`** | Intercepts `teleop`, `record`, or `eval` execution to modify arguments or swap target binaries. | Live YOLO camera wrapping, MuJoCo simulation loops, RealSense depth toggles |
| **`ServicePlugin`** | Manages lifecycle (start/stop/status) of background daemons and web servers. | Next.js visualizer frontend (port 3000) + FastAPI annotation backend (port 7861) |

---

## 5. Next Steps
* Learn the full technical contract in [Plugin Contract Specification](contract_specification.md).
* Build your own plugin in [Developing Custom Plugins](developing_plugins.md).
* Learn how dataset tools chain together in [Composable Dataset Pipelines](dataset_pipelines.md).
