"""Adapter plugin for lerobot-vision-detector.

Bridges real-time multi-camera YOLO wrapping and offline dataset augmentation
into CLIrobot's CLI, TUI, CommandRunner, and Dataset Pipelines.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any, Optional
import typer
from rich.panel import Panel
from rich.table import Table

from clirobot.plugins.base import (
    BasePlugin,
    DatasetTransformPlugin,
    DatasetTransformResult,
    DatasetTransformSpec,
    ExecutionPlan,
    PluginContext,
    PluginMetadata,
    RuntimeMiddlewarePlugin,
    TUIMenuContribution,
)
from clirobot.doctor.checker import CheckItem
from clirobot.tui.menu import MenuItem
from clirobot.ui.console import console, print_error, print_info, print_success


class VisionDetectorPlugin(DatasetTransformPlugin, RuntimeMiddlewarePlugin):
    """Adapter for lerobot-vision-detector integrating YOLO spatial cues into CLIrobot."""

    metadata = PluginMetadata(
        id="vision-detector",
        name="LeRobot Vision Detector",
        version="0.1.0",
        description="Real-time multi-camera YOLO wrapping & offline dataset augmentation (bounding boxes & segmentation masks).",
        category="vision",
        author="SinfonIA UniAndes",
    )

    def _resolve_vision_repo(self) -> Optional[Path]:
        """Locate sibling lerobot-vision-detector directory if present."""
        clirobot_dir = Path(__file__).resolve().parent.parent.parent.parent
        workspace_root = clirobot_dir.parent
        candidate = workspace_root / "lerobot-vision-detector"
        if candidate.is_dir():
            return candidate
        return None

    def is_available(self) -> tuple[bool, str]:
        try:
            import lerobot_vision_detector  # noqa: F401
            return True, "Installed as Python package"
        except ImportError:
            repo = self._resolve_vision_repo()
            if repo and (repo / "lerobot_vision_detector").is_dir():
                return True, f"Found in workspace ({repo.name})"
            return False, "Package lerobot-vision-detector not found"

    # ==========================================================================
    # Capability: DatasetTransformPlugin (Offline Augmentation)
    # ==========================================================================

    def get_transforms(self) -> list[DatasetTransformSpec]:
        return [
            DatasetTransformSpec(
                id="vision-augment",
                name="YOLO Vision Augmentation",
                description="Detect objects & render bounding boxes or segmentation masks onto specified camera feeds.",
                icon="👁️",
                supports_in_place=False,
                supports_dry_run=True,
                supports_hub_push=True,
            )
        ]

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
        if transform_id != "vision-augment":
            raise ValueError(f"Unknown transform_id: {transform_id}")

        cameras = kwargs.get("cameras", ["cam_high"])
        if isinstance(cameras, str):
            cameras = [c.strip() for c in cameras.split(",") if c.strip()]
        mode = kwargs.get("mode", "bbox")
        target_objects = kwargs.get("target_objects", None)
        if isinstance(target_objects, str):
            target_objects = [t.strip() for t in target_objects.split(",") if t.strip()]
        model_name = kwargs.get("model_name", None)
        conf_threshold = float(kwargs.get("conf_threshold", 0.25))

        if dry_run:
            ctx.console.print(
                Panel(
                    f"[bold cyan]Vision Augmentation Preview:[/bold cyan]\n"
                    f"  • Input Repo:       {input_repo}\n"
                    f"  • Output Repo:      {output_repo or 'outputs/<repo>'}\n"
                    f"  • Cameras:          {', '.join(cameras)}\n"
                    f"  • Modality:         {mode.upper()}\n"
                    f"  • Target Objects:   {target_objects or 'All COCO classes'}\n"
                    f"  • Model:            {model_name or 'Default'}\n"
                    f"  • Confidence:       {conf_threshold}\n"
                    f"  • Push to Hub:      {push_to_hub}",
                    title="[bold yellow]👁️ Vision Augmentation Dry Run[/bold yellow]",
                    border_style="yellow",
                )
            )
            return DatasetTransformResult(
                transform_id="vision-augment",
                success=True,
                input_repo_or_path=input_repo,
                output_path=output_dir,
                output_repo_id=output_repo,
                metrics={"mode": mode, "cameras": cameras, "dry_run": True},
            )

        # Run via CLI runner or Python API
        args = [
            f"--input_repo={input_repo}",
            f"--output_repo={output_repo or input_repo + '-detected'}",
            f"--mode={mode}",
            f"--conf_threshold={conf_threshold}",
        ]
        for c in cameras:
            args.extend(["--cameras", c])
        if target_objects:
            args.append(f"--target_objects={','.join(target_objects)}")
        if model_name:
            args.append(f"--model_name={model_name}")
        if output_dir:
            args.append(f"--output_dir={output_dir}")
        if push_to_hub:
            args.append("--push_to_hub")

        repo_dir = self._resolve_vision_repo()
        script_args = ["-m", "lerobot_vision_detector.cli.augment"] + args
        exit_code = ctx.runner.run(
            "vision-augment",
            script_args,
        )

        return DatasetTransformResult(
            transform_id="vision-augment",
            success=(exit_code == 0),
            input_repo_or_path=input_repo,
            output_path=output_dir,
            output_repo_id=output_repo,
            metrics={"exit_code": exit_code, "mode": mode, "cameras": cameras},
        )

    def run_interactive_wizard(self, transform_id: str, ctx: PluginContext) -> None:
        from rich.prompt import Confirm, Prompt

        profile = ctx.active_profile
        repo = Prompt.ask("Input dataset repo ID or local path", default=profile.dataset_repo_id)
        out_repo = Prompt.ask("Output dataset repo ID", default=f"{repo}-detected")
        cams_str = Prompt.ask(
            "Cameras to augment (comma-separated, unspecified remain untouched)",
            default=",".join(profile.cameras.keys()) if profile.cameras else "cam_high",
        )
        mode = Prompt.ask("Detection mode", choices=["bbox", "seg", "both"], default="bbox")
        targets = Prompt.ask("Target object classes (comma-separated, blank for all)", default="")
        push_hub = Confirm.ask("Push augmented dataset to Hugging Face Hub?", default=False)

        cams = [c.strip() for c in cams_str.split(",") if c.strip()]
        t_list = [t.strip() for t in targets.split(",") if t.strip()] if targets else None

        self.execute_transform(
            "vision-augment",
            ctx,
            input_repo=repo,
            output_repo=out_repo,
            cameras=cams,
            mode=mode,
            target_objects=t_list,
            push_to_hub=push_hub,
        )

    # ==========================================================================
    # Capability: RuntimeMiddlewarePlugin (Live Multi-Camera Wrapping)
    # ==========================================================================

    def applies_to_commands(self) -> list[str]:
        return ["record", "teleoperate", "teleop", "eval"]

    def mutate_execution_plan(
        self,
        plan: ExecutionPlan,
        ctx: PluginContext,
        runtime_options: Optional[dict[str, Any]] = None,
    ) -> ExecutionPlan:
        cfg = ctx.get_plugin_config("vision-detector", {})
        opts = runtime_options or {}

        # Enable if configured in profile or passed as runtime option
        is_enabled = opts.get("with_vision", False) or cfg.get("enabled", False)
        if not is_enabled:
            return plan

        mode = opts.get("vision_mode") or cfg.get("mode", "bbox")
        cameras = opts.get("vision_cameras") or cfg.get("cameras", "all")
        target_objects = opts.get("vision_targets") or cfg.get("target_objects", None)
        model_name = opts.get("vision_model") or cfg.get("model_name", None)
        conf = opts.get("vision_conf") or cfg.get("conf_threshold", 0.25)

        # Inject vision flags
        plan.args.append("--detector.enabled=true")
        plan.args.append(f"--detector.mode={mode}")
        if cameras and cameras != "all":
            c_str = ",".join(cameras) if isinstance(cameras, list) else str(cameras)
            plan.args.append(f"--detector.cameras={c_str}")
        if target_objects:
            t_str = ",".join(target_objects) if isinstance(target_objects, list) else str(target_objects)
            plan.args.append(f"--detector.target_objects={t_str}")
        if model_name:
            plan.args.append(f"--detector.model_name={model_name}")
        plan.args.append(f"--detector.conf_threshold={conf}")

        # Swap target module if executing directly
        cmd = plan.command_key
        if cmd in ("record", "lerobot-record"):
            plan.executable_override = (sys.executable, ["-m", "lerobot_vision_detector.cli.record"])
        elif cmd in ("teleop", "teleoperate", "lerobot-teleoperate"):
            plan.executable_override = (sys.executable, ["-m", "lerobot_vision_detector.cli.teleoperate"])
        elif cmd in ("eval", "lerobot-eval"):
            plan.executable_override = (sys.executable, ["-m", "lerobot_vision_detector.cli.eval_policy"])

        return plan

    # ==========================================================================
    # CLI Commands & Sub-apps
    # ==========================================================================

    def register_cli(self, root_app: typer.Typer, sub_apps: dict[str, typer.Typer]) -> None:
        vision_app = typer.Typer(
            name="vision",
            help="Computer vision detection & camera wrapping for LeRobot (YOLO/open-vocab).",
            no_args_is_help=False,
        )

        @vision_app.command("classes")
        def list_classes(
            model: str = typer.Option("yolov8n.pt", "--model", "-m", help="Model name or weights path"),
            search: Optional[str] = typer.Option(None, "--search", "-s", help="Filter class names"),
            as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
        ):
            """List all detectable object classes for a vision/YOLO model."""
            from clirobot.config.manager import ConfigManager
            from clirobot.integration.runner import CommandRunner

            runner = CommandRunner(ConfigManager())
            args = ["-m", "lerobot_vision_detector.cli.list_classes", f"--model={model}"]
            if search:
                args.extend(["--search", search])
            if as_json:
                args.append("--json")
            runner.run("vision-classes", args)

        @vision_app.command("augment")
        def augment_cmd(
            input_repo: str = typer.Option(..., "--input-repo", "-i", help="Input dataset repo ID or path"),
            output_repo: str = typer.Option(..., "--output-repo", "-o", help="Destination dataset repo ID"),
            cameras: list[str] = typer.Option(["cam_high"], "--camera", "-c", help="Camera(s) to augment"),
            mode: str = typer.Option("bbox", "--mode", "-m", help="Modality: bbox, seg, or both"),
            target_objects: Optional[str] = typer.Option(None, "--target-objects", "-t", help="Target object classes comma-separated"),
            model_name: Optional[str] = typer.Option(None, "--model", help="YOLO model path or name"),
            conf: float = typer.Option(0.25, "--conf", help="Confidence threshold"),
            push_to_hub: bool = typer.Option(False, "--push-to-hub", help="Upload to Hugging Face Hub"),
            dry_run: bool = typer.Option(False, "--dry-run", help="Preview augmentation without running"),
        ):
            """Augment offline LeRobot dataset with YOLO bounding boxes or segmentation masks."""
            from clirobot.config.manager import ConfigManager
            from clirobot.integration.runner import CommandRunner

            ctx = PluginContext(ConfigManager(), CommandRunner(), console)
            t_list = [t.strip() for t in target_objects.split(",") if t.strip()] if target_objects else None
            self.execute_transform(
                "vision-augment",
                ctx,
                input_repo=input_repo,
                output_repo=output_repo,
                cameras=cameras,
                mode=mode,
                target_objects=t_list,
                model_name=model_name,
                conf_threshold=conf,
                push_to_hub=push_to_hub,
                dry_run=dry_run,
            )

        root_app.add_typer(vision_app, name="vision", help="YOLO multi-camera wrapping & dataset augmentation")

        # Also add augment to `clirobot dataset augment`
        if "dataset" in sub_apps:
            dataset_app = sub_apps["dataset"]

            @dataset_app.command("augment")
            def dataset_augment_alias(
                input_repo: Optional[str] = typer.Option(None, "--input-repo", "-i", help="Input dataset repo ID"),
                output_repo: Optional[str] = typer.Option(None, "--output-repo", "-o", help="Target dataset repo ID"),
                cameras: list[str] = typer.Option(["cam_high"], "--camera", "-c", help="Camera(s) to augment"),
                mode: str = typer.Option("bbox", "--mode", "-m", help="Detection modality: bbox or seg"),
                target_objects: Optional[str] = typer.Option(None, "--targets", "-t", help="Target object classes"),
                push_to_hub: bool = typer.Option(False, "--push-to-hub", help="Push to Hugging Face Hub"),
                dry_run: bool = typer.Option(False, "--dry-run", help="Dry-run preview"),
            ):
                """Augment dataset with YOLO bounding boxes or masks (alias for vision augment)."""
                from clirobot.config.manager import ConfigManager
                from clirobot.integration.runner import CommandRunner

                mgr = ConfigManager()
                target_in = input_repo or mgr.get_active_profile().dataset_repo_id
                target_out = output_repo or f"{target_in}-detected"
                ctx = PluginContext(mgr, CommandRunner(mgr), console)
                t_list = [t.strip() for t in target_objects.split(",") if t.strip()] if target_objects else None
                self.execute_transform(
                    "vision-augment",
                    ctx,
                    input_repo=target_in,
                    output_repo=target_out,
                    cameras=cameras,
                    mode=mode,
                    target_objects=t_list,
                    push_to_hub=push_to_hub,
                    dry_run=dry_run,
                )

    # ==========================================================================
    # TUI Contributions
    # ==========================================================================

    def get_tui_contributions(self, ctx: PluginContext) -> list[TUIMenuContribution]:
        return [
            TUIMenuContribution(
                target_menu="datasets",
                item=MenuItem(
                    id="vision_augment",
                    label="Augment Dataset with YOLO Vision",
                    icon="👁️",
                    description="Render bounding boxes or segmentation masks onto selected camera streams.",
                ),
                handler=lambda c: self.run_interactive_wizard("vision-augment", c),
                order=25,
            ),
            TUIMenuContribution(
                target_menu="control",
                item=MenuItem(
                    id="toggle_vision",
                    label="Toggle Live YOLO Camera Wrapping",
                    icon="👁️",
                    description="Enable or disable real-time vision detection during teleop/recording.",
                ),
                handler=self._tui_toggle_vision,
                order=50,
            ),
        ]

    def _tui_toggle_vision(self, ctx: PluginContext) -> None:
        from rich.prompt import Confirm, Prompt

        cfg = ctx.get_plugin_config("vision-detector", {"enabled": False, "mode": "bbox"})
        cur_status = cfg.get("enabled", False)
        console.print(f"\n[bold cyan]Live YOLO Camera Wrapping[/bold cyan] (Current: [bold]{'ENABLED' if cur_status else 'DISABLED'}[/bold])\n")
        new_status = Confirm.ask("Enable live YOLO camera wrapping for teleop/record?", default=not cur_status)
        cfg["enabled"] = new_status
        if new_status:
            cfg["mode"] = Prompt.ask("Detection mode", choices=["bbox", "seg", "both"], default=cfg.get("mode", "bbox"))
            cfg["target_objects"] = Prompt.ask("Target object classes (blank for all)", default=cfg.get("target_objects", ""))
            cfg["model_name"] = Prompt.ask("Model name / path", default=cfg.get("model_name", "yolov8n.pt"))
        ctx.save_plugin_config("vision-detector", cfg)
        print_success(f"Updated live vision settings! (Enabled: {new_status})")

    # ==========================================================================
    # Doctor Checks
    # ==========================================================================

    def run_doctor_checks(self, ctx: PluginContext) -> list[CheckItem]:
        checks = []
        is_avail, reason = self.is_available()
        checks.append(
            CheckItem(
                category="Vision Plugin",
                name="Vision Detector Package",
                status="PASS" if is_avail else "WARN",
                detail=reason,
                recommendation="" if is_avail else "Run: pip install -e lerobot-vision-detector",
            )
        )

        # Check ultralytics
        ultralytics_found = False
        try:
            import ultralytics  # noqa: F401
            ultralytics_found = True
        except ImportError:
            pass

        checks.append(
            CheckItem(
                category="Vision Plugin",
                name="Ultralytics YOLO Backend",
                status="PASS" if ultralytics_found else "WARN",
                detail="Installed" if ultralytics_found else "ultralytics not installed in active environment",
                recommendation="" if ultralytics_found else "Run: uv pip install ultralytics",
            )
        )

        return checks
