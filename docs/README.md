# CLIrobot Documentation

Welcome to the comprehensive documentation for **CLIrobot** (`clr`), the unified, ergonomic control hub for Hugging Face LeRobot.

---

## 📚 Documentation Index

### 🧩 Plugin System & Architecture
* [**Plugin System Overview**](plugins/overview.md): High-level architecture, design philosophy, discovery mechanisms, and capability mixins.
* [**Plugin Contract Specification**](plugins/contract_specification.md): Technical reference for all interfaces, protocols, and data structures (`BasePlugin`, `DatasetTransformPlugin`, `RuntimeMiddlewarePlugin`, `ServicePlugin`, `PluginContext`, `ExecutionPlan`).
* [**Developing Custom Plugins**](plugins/developing_plugins.md): Step-by-step tutorial on building, packaging, and testing a custom CLIrobot plugin from scratch.
* [**Composable Dataset Pipelines**](plugins/dataset_pipelines.md): Detailed guide on `DatasetPipelineEngine`, JSON/YAML recipe specifications, and multi-step dataset manipulation.
* [**Integrated Tools & Adapters**](plugins/integrated_plugins.md): In-depth guide on the four built-in tool adapters:
  1. `core-dataset` (Pruning, temporal splitting, annotation inspection)
  2. `vision-detector` (YOLO bounding boxes & segmentation masks)
  3. `embodied-data` (Physical/Sim recording, manual episode state machines, EE pose, depth)
  4. `dataset-visualizer` (Next.js/FastAPI 3D URDF visualizer & v3.1 language annotation backend)

---

## 🚀 Quick Navigation
* [Main Project README](../README.md)
* [System Diagnostics Guide](../README.md#%EF%B8%8F-global-settings--doctor)
* [Hardware Profile Configuration](../README.md#-profile-management)
* [Interactive TUI Guide](../README.md#%EF%B8%8F-interactive-tui-mode)
