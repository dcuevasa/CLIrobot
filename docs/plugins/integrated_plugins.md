# Integrated Tool Adapters

CLIrobot ships with four built-in tool adapters that bridge external robotics tools and libraries into unified CLI commands, interactive TUI menus, and composable dataset transforms.

---

## 1. ✂️ Core Dataset Manipulation (`core-dataset`)

The `core-dataset` plugin exposes high-performance dataset pruning, temporal annotation splitting, and inspection tools.

### Capabilities
* **`prune-dataset` (Transform)**:
  * Remove heavy depth images (e.g. `observation.images.wrist_depth`) to save 70%+ disk space.
  * Slice robot state and action dimensions (e.g. extract 6-DoF arm coordinates from 14-DoF bimanual datasets).
  * Automatically recompute and update `meta/stats.json` (min, max, mean, std) and `meta/info.json`.
  * Optional direct upload to Hugging Face Hub.
* **`split-dataset` (Transform)**:
  * Split monolithic datasets into targeted subtask episodes using `lerobot_annotations.json`.
  * Supports strategies: `subtask`, `task_aug`, `plan`, `vqa`, and `speech`.
  * Video re-encoding with ffmpeg to match trimmed timestamps.
* **`inspect-annotations` (Transform & CLI)**:
  * Analyze annotation distribution, average subtask lengths, and language instruction coverage.

### CLI Commands
```bash
# Prune depth channels and slice actions
clirobot dataset prune \
  --repo-id "lerobot/aloha_mobile" \
  --strip-depth \
  --slice-action "0:6" \
  --output-dir "./data/pruned"

# Split dataset by subtask annotations
clirobot dataset split \
  --repo-id "lerobot/so100_pick_place" \
  --strategy "subtask" \
  --min-episode-len 10 \
  --reencode-video

# Inspect annotations in terminal
clirobot dataset inspect-annotations --repo-id "lerobot/so100_pick_place"
```

---

## 2. 👁️ Vision Detector Adapter (`vision-detector`)

Adapts the [`lerobot-vision-detector`](https://github.com/huggingface/lerobot) tool to enable YOLO-based object detection, segmentation masks, and real-time bounding box overlays.

### Capabilities
* **Offline Dataset Augmentation**:
  * Runs YOLO (v8, v10, v11) across recorded camera frames (`camera_top`, `camera_wrist`).
  * Injects bounding boxes, class labels, and confidence scores into dataset metadata or generates annotated video sidecars.
* **Real-Time Runtime Middleware**:
  * When enabled in a profile, wraps `clirobot teleop` or `clirobot record` camera feeds.
  * Overlays real-time bounding boxes and crosshairs directly on OpenCV camera preview streams.
* **Doctor Checks**:
  * Diagnostics for `ultralytics` installation, PyTorch CUDA acceleration, and webcam capture compatibility.

### CLI Commands
```bash
# Run YOLO detection offline on a dataset
clirobot vision augment \
  --repo-id "user/so100-demo" \
  --model "yolov8m.pt" \
  --cameras "camera_top" \
  --conf 0.45 \
  --save-video

# Check vision detector environment health
clirobot doctor
```

### Profile Configuration
```json
{
  "plugin_configs": {
    "vision-detector": {
      "enabled": true,
      "model": "yolov8n.pt",
      "overlay_during_teleop": true,
      "confidence_threshold": 0.5
    }
  }
}
```

---

## 3. 🦾 Embodied Data Adapter (`embodied-data`)

Adapts [`FLAG-Embodied-data`](https://github.com/FlagOpen/FLAG-Embodied-data) high-rate physical robot recording, MuJoCo simulation, manual episode keybindings, and environment configuration scripts.

### Capabilities
* **Manual Episode State Machine**:
  * Intuitive hotkey flow: `[Enter]` to start recording, `[Space]` to pause/resume, `[Right]` to save episode, `[Esc]` to abort/discard.
  * Instant RAM buffer clearing when an episode is discarded (no corrupted episodes).
* **Physical Robot Recording**:
  * 50Hz synchronized leader/follower control loop.
  * Automatic End-Effector (EE) pose computation and RealSense depth stream injection (`use_depth: true`).
* **MuJoCo Simulation Recording**:
  * Record synthetic demonstration datasets in simulation environments using identical teleop keybindings.
* **Environment Configuration Importer**:
  * Import legacy `set_variables.sh` scripts directly into CLIrobot hardware profiles.

### CLI Commands
```bash
# Record physical robot demonstration with manual hotkey control
clirobot record physical \
  --fps 50 \
  --num-episodes 20 \
  --enable-depth

# Record in MuJoCo simulation
clirobot record sim \
  --task "PickPlace" \
  --headless false

# Import legacy bash variables into active profile
clirobot profile import-env set_variables.sh
```

### Profile Camera Schema with Depth
```json
{
  "cameras": {
    "wrist": {
      "type": "intelrealsense",
      "serial": "12345678",
      "width": 640,
      "height": 480,
      "fps": 30,
      "use_depth": true
    }
  }
}
```

---

## 4. 🌐 Dataset Visualizer & Web Studio (`dataset-visualizer`)

Adapts the [`lerobot-dataset-visualizer`](https://github.com/huggingface/lerobot) Next.js 3D web studio and FastAPI backend.

### Capabilities
* **3D Robot Arm & URDF Visualization**:
  * Interactive 3D web viewer rendering the robot's physical URDF model synchronized with recorded joint angles.
  * Multi-camera viewpoint playback and end-effector trajectory trails.
* **Service Lifecycle Management**:
  * Manage background daemon processes (FastAPI backend on port 7861 and Next.js frontend on port 3000).
  * Check status, inspect logs, and cleanly terminate processes.
* **Dataset Export & Hub Sync**:
  * Export datasets to Parquet v3.1 format with joint annotations.
  * Upload reviewed datasets directly to Hugging Face Hub.

### CLI Commands
```bash
# Start background visualizer services (Next.js + FastAPI)
clirobot visualizer start

# Check service health and active ports
clirobot visualizer status

# Export dataset with URDF joint transforms
clirobot visualizer export \
  --repo-id "user/so100-demo" \
  --format "parquet_v3_1"

# Stop background services
clirobot visualizer stop
```

---

## 🖥️ TUI Integration

All four plugins contribute dedicated interactive actions to the CLIrobot TUI menu:
* **Control Menu**: Launch physical recording, MuJoCo simulation, and audio cues.
* **Datasets Menu**: Run dataset transforms, launch 3D URDF visualizer, inspect annotations.
* **Plugins Menu (`🧩 Plugins & Extensions`)**: Inspect plugin statuses, toggle plugins, and view doctor diagnostics.
