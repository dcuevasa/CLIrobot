"""Constants and configuration paths for CLIrobot."""

from pathlib import Path

# Configuration directories
CONFIG_DIR = Path.home() / ".config" / "clirobot"
CONFIG_FILE = CONFIG_DIR / "config.json"
BACKUP_DIR = CONFIG_DIR / "backups"
CALIBRATION_BACKUP_DIR = BACKUP_DIR / "calibration"

# LeRobot standard cache paths
HF_CACHE_DIR = Path.home() / ".cache" / "huggingface" / "lerobot"
LEGACY_CACHE_DIR = Path.home() / ".cache" / "lerobot"

# Supported robot types in LeRobot ecosystem
SUPPORTED_ROBOTS = [
    "so100",
    "so101",
    "koch",
    "koch_bimanual",
    "aloha",
    "lekiwi",
    "moss",
    "reachy2",
    "custom",
]

# Supported teleoperators
SUPPORTED_TELEOPERATORS = [
    "so100_leader",
    "so101_leader",
    "koch_leader",
    "bi_so_leader",
    "koch_bimanual_leader",
    "aloha_leader",
    "keyboard",
    "gamepad",
    "custom",
]

# Common camera names
COMMON_CAMERA_NAMES = [
    "laptop",
    "wrist",
    "overhead",
    "phone",
    "cam_high",
    "cam_low",
    "cam_left_wrist",
    "cam_right_wrist",
]

# Supported policy types for training
SUPPORTED_POLICIES = [
    "act",
    "diffusion",
    "tdmpc",
    "vqbet",
    "smolvlm",
]

# Mapping of LeRobot CLI commands to their script modules
LEROBOT_COMMANDS_MAP = {
    "find-port": "lerobot.scripts.lerobot_find_port",
    "find-cameras": "lerobot.scripts.lerobot_find_cameras",
    "setup-motors": "lerobot.scripts.lerobot_setup_motors",
    "calibrate": "lerobot.scripts.lerobot_calibrate",
    "find-joint-limits": "lerobot.scripts.lerobot_find_joint_limits",
    "setup-can": "lerobot.scripts.lerobot_setup_can",
    "teleoperate": "lerobot.scripts.lerobot_teleoperate",
    "record": "lerobot.scripts.lerobot_record",
    "replay": "lerobot.scripts.lerobot_replay",
    "train": "lerobot.scripts.lerobot_train",
    "eval": "lerobot.scripts.lerobot_eval",
    "rollout": "lerobot.scripts.lerobot_rollout",
    "annotate": "lerobot.scripts.lerobot_annotate",
    "edit-dataset": "lerobot.scripts.lerobot_edit_dataset",
    "dataset-viz": "lerobot.scripts.lerobot_dataset_viz",
    "imgtransform-viz": "lerobot.scripts.lerobot_imgtransform_viz",
    "info": "lerobot.scripts.lerobot_info",
    "train-tokenizer": "lerobot.scripts.lerobot_train_tokenizer",
    "convert-dcp": "lerobot.scripts.lerobot_convert_dcp",
    "build-mp4-sidecar": "lerobot.scripts.lerobot_build_mp4_sidecar",
}

# Binary names for LeRobot CLI
LEROBOT_BINARIES_MAP = {
    key: f"lerobot-{key}" for key in LEROBOT_COMMANDS_MAP
}
