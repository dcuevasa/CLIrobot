# ⚡ CLIrobot (clr)

<div align="center">

```
   ██████╗██╗     ██╗██████╗  ██████╗ ██████╗  ██████╗ ████████╗
  ██╔════╝██║     ██║██╔══██╗██╔═══██╗██╔══██╗██╔═══██╗╚══██╔══╝
  ██║     ██║     ██║██████╔╝██║   ██║██████╔╝██║   ██║   ██║   
  ██║     ██║     ██║██╔══██╗██║   ██║██╔══██╗██║   ██║   ██║   
  ╚██████╗███████╗██║██║  ██║╚██████╔╝██████╔╝╚██████╔╝   ██║   
   ╚═════╝╚══════╝╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝  ╚═════╝    ╚═╝   
```

### **The Unified, Ergonomic Control Hub for Hugging Face LeRobot**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)
[![Code Style: Rich](https://img.shields.io/badge/UI-Rich%20%2B%20Typer-cyan.svg)](https://github.com/Textualize/rich)
[![LeRobot Compatible](https://img.shields.io/badge/LeRobot-All%2020%20Commands-yellow.svg)](https://github.com/huggingface/lerobot)

*Smart hardware profiles • Plug-and-detect port wizards • Visual calibration management • Robust multi-backend keyboard control*

---

</div>

## 📖 Overview

**CLIrobot** (`clirobot` or `clr`) transforms the Hugging Face [LeRobot](https://github.com/huggingface/lerobot) command-line experience into a unified, visually polished, and reliable CLI hub.

Standard LeRobot commands (`lerobot-find-port`, `lerobot-record`, `lerobot-teleoperate`, `lerobot-calibrate`, etc.) are powerful, but daily robotics operation often suffers from friction:
* 🔌 **Port swapping nightmare**: Rebooting or reconnecting USB cables swaps `/dev/ttyACM0` and `/dev/ttyACM1`. You are constantly copying long port paths into 150-character terminal commands.
* ⌨️ **Broken keyboard inputs**: Regular LeRobot scripts struggle with keyboard capture. Over SSH, headless sessions, Wayland, or inside Docker, `pynput` crashes with `DisplayNameError` or drops keystrokes. When OpenCV camera windows are focused, terminal keys are ignored; and if a script crashes, the terminal is left in a broken, echo-disabled raw mode.
* 🗃️ **Lost calibrations**: Calibration files live deep in cache directories (`~/.cache/huggingface/lerobot/calibration/`), making it difficult to inspect joint offsets, compare changes, or back up configurations.
* 📷 **Camera index confusion**: Which camera is index 0 vs index 1 (wrist vs overhead)? Standard tools require guesswork.
* 🧩 **Command fragmentation**: 20 separate commands each requiring custom flags and manual repetition.

**CLIrobot solves all of this out-of-the-box.**

---

## ✨ Key Features

| Feature | Standard LeRobot | CLIrobot (`clr`) |
| :--- | :--- | :--- |
| **Interface** | CLI commands only | Interactive TUI menu with arrow keys + Direct CLI commands |
| **UI & Experience** | Raw terminal output | Rich color-coded tables, status panels, HUDs, and spinners |
| **Port Management** | Prints ports; manual copy-pasting | 1-click list select, interactive plug-and-detect wizard, udev rules |
| **Keyboard Control** | Crashes on Wayland/SSH/Docker; loses focus | Cross-platform (Linux, Windows, macOS) native reader + OpenCV bridge |
| **Recording QoL** | Rigid flow, long encoding pauses | Hotkey flow (Enter/Right/Left/Space/Esc), buffer clearing, Rerun viz, sound cues, streaming encode |
| **Dataset Pruning** | Manual custom scripts | 1-command depth stripping, 6-DoF/custom EE slicing, metadata sync, Hub upload |
| **Annotation Splitting** | Monolithic datasets | Strategy-based splitting (subtask, task_aug, plan, VQA, speech), video re-encoding, Hub push |
| **Calibration** | Hidden JSON files in cache | List, inspect joints visually, backup, restore, diff, export/import |
| **Camera Setup** | Guess index 0, 1, 2 | 1-click list select, instant ASCII terminal preview, role binding |
| **Profile Switcher** | Re-type all flags every session | Switch profiles (`so100-desk`, `so101-lab`, `koch-bimanual`, `aloha`) in 1 command |
| **Coverage** | Fragmented scripts | Unified hub with full LeRobot command map and dataset tools |

---

## 🖥️ Interactive TUI Mode

Whenever you write just **`clirobot`** (or **`clr`**), an interactive terminal interface launches automatically:

```bash
clirobot
```

```
   ██████╗██╗     ██╗██████╗  ██████╗ ██████╗  ██████╗ ████████╗
  ██╔════╝██║     ██║██╔══██╗██╔═══██╗██╔══██╗██╔═══██╗╚══██╔══╝
  ██║     ██║     ██║██████╔╝██║   ██║██████╔╝██║   ██║   ██║   
  ██║     ██║     ██║██╔══██╗██║   ██║██╔══██╗██║   ██║   ██║   
  ╚██████╗███████╗██║██║  ██║╚██████╔╝██████╔╝╚██████╔╝   ██║   
   ╚═════╝╚══════╝╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝  ╚═════╝    ╚═╝   

  ⚡ Unified Ergonomic Hub for Hugging Face LeRobot ⚡
  Profile: so100-desk (so100) | Leader: /dev/ttyACM0 | Follower: /dev/ttyACM1

📍 Home
Select an option using arrow keys [↑/↓] and press Enter:

  ❯ 🎮 Robotics Control & Teleop      Launch teleoperation, recording, or replay
    🔌 Hardware & Connections         Select ports, setup cameras, view previews
    👤 Profiles & Configuration       Switch robot profile or edit parameters
    🗜️ Calibration Files Manager       Inspect joint offsets, diff, or backup
    📊 Datasets & Visualization       Rerun visualizer, edit episodes, sidecars
    🩺 System Doctor Diagnostics       Check Python, LeRobot, serial permissions
    ⌨️ Keyboard Diagnostics & Test    Test latency and cross-platform key capture
    🚪 Exit CLIrobot                  Return to terminal shell

Navigation: [↑/↓] Move Selection • [Enter] Select • [Esc/b] Back • [q] Exit TUI
```

* Navigate menus smoothly with your arrow keys `↑`/`↓` and `Enter`.
* Select ports and cameras directly from detected lists without typing device names.
* Hit `Esc` or `b` to step back, or `q` to return to your terminal prompt.
* Direct CLI commands (`clirobot teleop`, `clirobot record`, etc.) remain fully functional for terminal scripts and power users!

---

## 🚀 Quick Start

### 1. Installation

Clone and install `CLIrobot`:
```bash
git clone https://github.com/dcuevasa/CLIrobot.git
cd CLIrobot
pip install -r requirements.txt
pip install -e .
```


*(Optional) Enable shell completions:*
```bash
clirobot --install-completion
```

### 2. Launch Interactive TUI or Run Doctor
```bash
# Launch interactive TUI hub
clirobot

# Or run environment diagnostic directly
clirobot doctor
```

### 3. Identify and Assign Robot Ports
Launch the guided plug-and-detect wizard or pick from the detected ports list:
```bash
# From TUI: Hardware & Connections -> Assign Leader/Follower Port
# Or via CLI:
clirobot ports find
```

### 4. Teleoperate & Record Instantly
No need to type long port arguments:
```bash
# Live teleoperation with active profile ports & camera feeds
clirobot teleop

# Record 10 demonstration episodes with real-time keyboard HUD
clirobot record --episodes 10 --task "Pick red block"
```


---

## ⌨️ Robust Keyboard Subsystem

### Why Regular LeRobot Struggled
1. **The SSH / Wayland / Headless Wall**: `pynput` requires an active X11 display. In headless setups, remote SSH terminals, Docker, or Wayland, it fails or drops events silently.
2. **OpenCV Window Focus Trap**: When camera feeds are displayed (`cv2.imshow`), clicking the camera window directs OS focus to OpenCV. In standard LeRobot, keystrokes are lost because the terminal listener doesn't receive them.
3. **Mangled Terminal Raw State**: If an unhandled exception or Ctrl+C occurs during cbreak mode, the terminal shell is left with echo disabled and newlines broken.
4. **Escape Sequence Fragmentation**: Multi-byte ANSI sequences for arrow keys (e.g. `\x1b[C`) over high-latency SSH links get split or echoed as garbage `^[[C`.

### The CLIrobot Solution
* **Cross-Platform Native Input (Linux, Windows, macOS)**:
  * **Linux & macOS**: Non-blocking POSIX `select` with `termios` raw/cbreak mode and a timeout-aware state machine that reliably disambiguates standalone `Esc` from multi-byte ANSI sequences (`↑`, `↓`, `←`, `→`).
  * **Windows**: Native `msvcrt` unbuffered console reader handling standard ASCII and 2-byte extended key scan codes (`\x00` and `\xe0` prefix).
* **OpenCV Window Bridge**: Seamlessly translates `cv2.waitKey()` codes into canonical key events, so hotkeys work whether the terminal or camera window has focus.
* **Fail-Safe Cleanup Guarantee**: Uses `atexit` hooks and custom `SIGINT`/`SIGTERM`/`SIGHUP` handlers ensuring terminal attributes are **always** restored to sane defaults.
* **Interactive Diagnostic Test**: Test your terminal's keyboard capture latency and escape decoding:
  ```bash
  clirobot keyboard test
  ```


### Recording Hotkeys Reference
| Key | Action |
| :---: | :--- |
| `[SPACE]` or `[P]` | **Pause / Resume** recording episode |
| `[R]` or `[← Left]` | **Re-record** current episode (discards faulty run) |
| `[N]` or `[→ Right]` or `[S]` | **Save & Next** episode |
| `[Q]` or `[ESC]` | **Quit / Stop** session safely |

---

## 🔌 Hardware & Port Management

### Smart Plug-and-Detect Wizard
```bash
# Launch interactive port wizard
clirobot ports find

# Or list all detected USB ports
clirobot ports list

# Manually assign ports to profile
clirobot ports assign --leader /dev/ttyACM0 --follower /dev/ttyACM1
```

### Linux Permanent Symlinks (udev Rules)
Never worry about ports swapping after a reboot:
```bash
clirobot ports udev
```
Generates rules so your arms are permanently available at `/dev/lerobot-leader` and `/dev/lerobot-follower`.

---

## 📷 Camera Discovery & Terminal Snapshot Preview

Easily discover, test, and preview cameras:
```bash
# Scan all video devices
clirobot cameras scan

# Terminal Snapshot Preview (renders an ASCII/ANSI preview in your terminal!)
clirobot cameras preview 0

# Assign camera index to a role
clirobot cameras assign wrist 1 --width 1280 --height 720 --fps 30

# Guided camera setup wizard
clirobot cameras wizard
```

---

## 🗜️ Calibration Management

Manage calibration files stored in `~/.cache/huggingface/lerobot/calibration/`:

```bash
# List all saved calibration files
clirobot calibrate list

# Visually inspect joint homing offsets, travel ranges, and drive modes
clirobot calibrate inspect so100/main

# Compare two calibrations side-by-side with joint delta highlights
clirobot calibrate diff so100/main so100/backup_main

# Run calibration procedure (ports pre-injected from profile)
clirobot calibrate run --arm follower
clirobot calibrate run --arm leader

# Create timestamped backup of all calibrations
clirobot calibrate backup

# Restore calibrations from a backup archive
clirobot calibrate restore

# Export / Import calibrations
clirobot calibrate export so100/main ./my_calibration.json
clirobot calibrate import ./my_calibration.json --robot-type so100 --robot-id team_arm
```

---

## 🎥 Demonstration Recording & Quality-of-Life (QoL) Controls

CLIrobot enhances LeRobot demonstration recording with intuitive episode lifecycle controls, visual HUD feedback, buffer clearing, and asynchronous video streaming:

```bash
# Record with full QoL features enabled
clirobot record \
  --episodes 10 \
  --task "Pick up coffee pod" \
  --display-data \
  --streaming-encoding \
  --play-sounds \
  --reset-every-episode
```

### Hotkey Lifecycle & Buffer Management
* **`[ENTER]`**: Start recording episode (from waiting or warmup states).
* **`[RIGHT]`**: Accept & save episode (can accept early before countdown expiration).
* **`[LEFT]`**: Discard episode & clear buffer (`clear_episode_buffer()`), preventing partial or failed attempts from polluting the dataset.
* **`[SPACE]`**: Skip / redo attempt without saving.
* **`[ESC]` or `[Q]`**: Gracefully stop recording session and save all accepted episodes.

### QoL Flags
* **`--display-data` / `--rerun`**: Real-time Rerun visualizer streaming robot actions, joint states, and camera feeds.
* **`--streaming-encoding`**: Asynchronously encodes MP4 streams in worker threads so saving episodes is instantaneous without long end-of-episode freezing.
* **`--play-sounds`**: Auditory cues and TTS voice announcements for episode start, accept, discard, and finish.
* **`--reset-every-episode`**: Signals the environment / robot to reset home positions or scene objects between episodes.
* **`--resume`**: Safely resume recording into an existing dataset repository without overwriting existing episodes.

---

## 🧹 Dataset Pruning (`clirobot dataset prune`)

Prepare raw datasets for imitation learning architectures (ACT, Diffusion Policy, SmolVLA) by stripping redundant camera streams and slicing degrees of freedom:

```bash
# Strip heavy depth video streams and slice state/action vectors to 6 DoF
clirobot dataset prune \
  --repo-id "user/so101_raw_dataset" \
  --output "./pruned_dataset" \
  --drop-depth \
  --drop-ee

# Prune specific features and slice state/action to custom 4 DoF
clirobot dataset prune \
  --repo-id "./my_dataset" \
  --slice-dof 4 \
  --drop-feature "custom_sensor"

# Prune and upload directly to Hugging Face Hub
clirobot dataset prune \
  --repo-id "user/raw-dataset" \
  --output-repo-id "user/act-ready-dataset" \
  --drop-depth \
  --drop-ee \
  --push-to-hub
```

### What Pruning Does:
1. **Parquet Tables**: Drops depth observation columns and slices `observation.state` and `action` arrays to the desired DoF.
2. **Video Folders**: Recursively deletes matching depth video directories in `videos/chunk-*`.
3. **Metadata Synchronization**: Updates `meta/info.json` feature shapes, tensor names, and synchronizes `meta/stats.json` min/max/mean metrics.
4. **Structure Enforcement**: Standardizes loose metadata files into the compliant `meta/` directory structure.

---

## 🔪 Dataset Splitting by Annotations (`clirobot dataset split`)

Automatically segment complex multi-step demonstration datasets into subdatasets corresponding to individual subtasks, task augmentations, or high-level plans using visualizer annotations (`meta/lerobot_annotations.json` v2/v1 or parquet language columns):

```bash
# 1. Inspect annotations and coverage without writing files:
clirobot dataset annotations --repo-id "./my_dataset"

# 2. Split dataset by all subtasks:
clirobot dataset split \
  --repo-id "./my_dataset" \
  --output-dir "./subdatasets" \
  --annotation-type subtask

# 3. Extract a specific subtask and upload to Hugging Face Hub:
clirobot dataset split \
  --repo-id "user/so101-leader-v1" \
  --annotation-type subtask \
  --subtask "pick up coffee pod" \
  --push-to-hub \
  --hub-repo-prefix "user/so101-subtask-"
```

### Extensible Splitting Strategies:
* **`subtask` (Default)**: Consecutive subtask annotations `[t_k, t_{k+1})` are sliced into individual episodes with re-indexed frames, temporal alignment, and video re-encoding. First subtask automatically snaps to `0.0s` to prevent losing initial frames.
* **`task_aug`**: Groups and splits full episodes based on task augmentation labels.
* **`plan`**: Slices episodes based on high-level multi-step execution plans.
* **`vqa`**: Extracts temporal windows around visual question answering events.
* **`speech`**: Extracts windows around dialogue, interjections, and robot speech (`say` actions).

---

## 🎯 Modular Command Map (All LeRobot Features & Tools)

Every single LeRobot command is directly accessible, modular, and integrates with your active profile:

| CLIrobot Command | Underlying LeRobot Tool | Description |
| :--- | :--- | :--- |
| `clirobot ports find` | `lerobot-find-port` | Port discovery with auto-save to profile |
| `clirobot cameras scan` | `lerobot-find-cameras` | Camera scanning with terminal preview |
| `clirobot motors setup` | `lerobot-setup-motors` | Servo motor ID assignment and bus config |
| `clirobot calibrate run` | `lerobot-calibrate` | Joint zero-point & range calibration |
| `clirobot joint-limits` | `lerobot-find-joint-limits` | Measure physical min/max travel limits |
| `clirobot can setup` | `lerobot-setup-can` | CAN bus interface configuration |
| `clirobot teleop` | `lerobot-teleoperate` | Leader-follower teleoperation with HUD |
| `clirobot record` | `lerobot-record` | Dataset demonstration recording |
| `clirobot replay` | `lerobot-replay` | Replay episode on follower arm |
| `clirobot train` | `lerobot-train` | Train ACT / Diffusion / SmolVLM policies |
| `clirobot eval` | `lerobot-eval` | Evaluate policy on robot or gym sim |
| `clirobot rollout` | `lerobot-rollout` | Execute policy rollouts |
| `clirobot annotate` | `lerobot-annotate` | Annotate dataset episodes |
| `clirobot dataset edit` | `lerobot-edit-dataset` | Trim, filter, or merge dataset episodes |
| `clirobot dataset prune` | `clirobot dataset prune` | Prune depth streams, slice EE DoFs, sync metadata |
| `clirobot dataset split` | `clirobot dataset split` | Split dataset into subdatasets by annotations |
| `clirobot dataset annotations` | `clirobot dataset annotations` | Inspect & summarize visualizer annotations |
| `clirobot dataset viz` | `lerobot-dataset-viz` | Launch Rerun visualizer for datasets |
| `clirobot dataset transform-viz`| `lerobot-imgtransform-viz`| Visualize data augmentations |
| `clirobot dataset sidecar` | `lerobot-build-mp4-sidecar`| Build fast-streaming MP4 sidecars |
| `clirobot info` | `lerobot-info` | System and dataset metadata |
| `clirobot tokenizer train` | `lerobot-train-tokenizer` | Train action or vision tokenizers |
| `clirobot convert dcp` | `lerobot-convert-dcp` | Convert PyTorch distributed checkpoints |

### Arbitrary Argument Pass-Through & Dry-Run
You can pass any extra LeRobot flag to any command:
```bash
clirobot teleop --fps 60 --display_cameras=true
clirobot record --dataset.warmup_time_s=5.0
```
Want to verify the exact command line before running? Append `--dry-run`:
```bash
clirobot record --dry-run
```

You can also use the generic runner:
```bash
clirobot run record --dataset.num_episodes=5
```

---

## 👤 Profile Management

Store independent hardware configurations for multiple robots (e.g. `so100-desk`, `so101-lab`, `koch-bimanual`, `aloha`):

```bash
# List all profiles (active profile highlighted)
clirobot profile list

# Inspect active profile details
clirobot profile show

# Create a new profile (optionally cloned from existing)
clirobot profile create koch-desk --robot-type koch --clone-from default

# Switch active profile
clirobot profile switch koch-desk

# Export / Import profiles
clirobot profile export koch-desk ./koch.json
clirobot profile import ./koch.json
```

---

## 🛠️ Global Settings & Doctor

```bash
# Comprehensive diagnostic health check
clirobot doctor

# View global configuration
clirobot config show

# Set custom LeRobot python environment / binary path
clirobot config set lerobot_path /opt/conda/envs/lerobot
```

---

## 🧪 Running Tests

CLIrobot comes with a full automated test suite:

```bash
pytest -v
```

All 36 test cases cover configuration serialization, port enumeration, udev rule generation, calibration inspection, diffing, keyboard readers, OpenCV bridges, dataset pruning, annotation-based splitting, recording QoL flags, and CLI execution.

---

## 📄 License

Licensed under the [Apache License 2.0](LICENSE).