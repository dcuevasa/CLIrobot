"""Calibration files management, discovery, backups, restore, and export/import."""

import os
import shutil
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from clirobot.constants import HF_CACHE_DIR, LEGACY_CACHE_DIR, CALIBRATION_BACKUP_DIR
from clirobot.ui.console import console, print_info, print_success, print_warning, print_error, create_table


@dataclass
class CalibrationFileInfo:
    """Metadata for a LeRobot calibration file."""
    path: Path
    robot_type: str
    robot_id: str
    modified_time: datetime
    size_bytes: int
    data: dict

    @property
    def filename(self) -> str:
        return self.path.name


class CalibrationManager:
    """Manages LeRobot calibration files across Hugging Face cache and custom locations."""

    def __init__(self, custom_cache_dir: Path | None = None, include_global_cache: bool = True):
        self.custom_cache_dir = custom_cache_dir
        self.include_global_cache = include_global_cache
        self.cache_dirs: list[Path] = []
        if custom_cache_dir:
            self.cache_dirs.append(custom_cache_dir)
        if include_global_cache:
            self.cache_dirs.extend([
                HF_CACHE_DIR / "calibration",
                LEGACY_CACHE_DIR / "calibration",
            ])
        if custom_cache_dir and not include_global_cache:
            self.backup_dir = custom_cache_dir / "backups"
        else:
            self.backup_dir = CALIBRATION_BACKUP_DIR
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def get_primary_cache_dir(self) -> Path:
        """Returns the primary target directory for writing calibration files."""
        if self.custom_cache_dir and not self.include_global_cache:
            primary = self.custom_cache_dir
        else:
            primary = HF_CACHE_DIR / "calibration"
        primary.mkdir(parents=True, exist_ok=True)
        return primary


    def list_calibrations(self) -> list[CalibrationFileInfo]:
        """Scan all cache directories and return metadata for found calibration files."""
        results: list[CalibrationFileInfo] = []
        seen_paths: set[Path] = set()

        for base_dir in self.cache_dirs:
            if not base_dir.exists():
                continue

            for json_path in base_dir.rglob("*.json"):
                if json_path in seen_paths or any("backup" in p.lower() for p in json_path.parts):
                    continue
                seen_paths.add(json_path)


                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    # Deduce robot_type and arm_id from path structure:
                    # e.g. ~/.cache/.../calibration/<robot_type>/<arm_id>.json
                    parts = json_path.relative_to(base_dir).parts
                    if len(parts) >= 2:
                        robot_type = parts[0]
                        robot_id = parts[1].replace(".json", "")
                    else:
                        robot_type = "unknown"
                        robot_id = json_path.stem

                    stat = json_path.stat()
                    results.append(
                        CalibrationFileInfo(
                            path=json_path,
                            robot_type=robot_type,
                            robot_id=robot_id,
                            modified_time=datetime.fromtimestamp(stat.st_mtime),
                            size_bytes=stat.st_size,
                            data=data,
                        )
                    )
                except Exception as e:
                    continue

        return sorted(results, key=lambda x: x.modified_time, reverse=True)

    def get_calibration(self, identifier: str) -> CalibrationFileInfo | None:
        """Lookup calibration by filename, robot_type/robot_id, or full path."""
        for item in self.list_calibrations():
            if (
                item.path.name == identifier
                or item.path.stem == identifier
                or f"{item.robot_type}/{item.robot_id}" == identifier
                or str(item.path) == identifier
            ):
                return item
        return None

    def backup(self, identifier: str | None = None) -> list[Path]:
        """Create a timestamped backup of one or all calibration files."""
        items = [self.get_calibration(identifier)] if identifier else self.list_calibrations()
        items = [i for i in items if i is not None]

        if not items:
            return []

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_dir = self.backup_dir / f"backup_{timestamp}"
        dest_dir.mkdir(parents=True, exist_ok=True)

        backed_up: list[Path] = []
        for item in items:
            dest_file = dest_dir / f"{item.robot_type}_{item.robot_id}.json"
            shutil.copy2(item.path, dest_file)
            backed_up.append(dest_file)

        return backed_up

    def list_backups(self) -> list[tuple[str, list[Path]]]:
        """List all available backup archives."""
        if not self.backup_dir.exists():
            return []

        backups = []
        for backup_path in sorted(self.backup_dir.glob("backup_*"), reverse=True):
            if backup_path.is_dir():
                files = list(backup_path.glob("*.json"))
                backups.append((backup_path.name, files))
        return backups

    def restore_backup(self, backup_name: str) -> int:
        """Restore all files from a specific backup folder into the primary cache."""
        target_backup = self.backup_dir / backup_name
        if not target_backup.exists() or not target_backup.is_dir():
            raise FileNotFoundError(f"Backup {backup_name} not found.")

        restored_count = 0
        primary_cache = self.get_primary_cache_dir()

        for json_file in target_backup.glob("*.json"):
            # filenames are formatted as <robot_type>_<robot_id>.json
            stem = json_file.stem
            parts = stem.split("_", 1)
            if len(parts) == 2:
                robot_type, robot_id = parts
                dest_dir = primary_cache / robot_type
            else:
                dest_dir = primary_cache / "imported"
                robot_id = stem

            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_file = dest_dir / f"{robot_id}.json"
            shutil.copy2(json_file, dest_file)
            restored_count += 1

        return restored_count

    def export_calibration(self, identifier: str, dest_path: Path) -> Path:
        """Export a calibration file to the specified destination path."""
        item = self.get_calibration(identifier)
        if not item:
            raise FileNotFoundError(f"Calibration '{identifier}' not found.")

        dest_path = dest_path.resolve()
        if dest_path.is_dir():
            dest_path = dest_path / f"{item.robot_type}_{item.robot_id}.json"

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item.path, dest_path)
        return dest_path

    def import_calibration(self, src_path: Path, robot_type: str, robot_id: str) -> Path:
        """Import an external calibration JSON file into the primary LeRobot cache."""
        src_path = src_path.resolve()
        if not src_path.exists():
            raise FileNotFoundError(f"Source file {src_path} does not exist.")

        primary_cache = self.get_primary_cache_dir()
        dest_dir = primary_cache / robot_type
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / f"{robot_id}.json"

        shutil.copy2(src_path, dest_file)
        return dest_file

    def delete_calibration(self, identifier: str) -> bool:
        """Delete a calibration file from the cache."""
        item = self.get_calibration(identifier)
        if not item:
            return False

        item.path.unlink()
        return True
