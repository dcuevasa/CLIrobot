"""Adapter plugin for lerobot-dataset-visualizer.

Provides service lifecycle management (FastAPI backend + Next.js web frontend)
and REST client commands for v3.1 language annotation Parquet export & Hugging Face Hub sync.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Optional
import typer
from rich.panel import Panel

from clirobot.plugins.base import (
    BasePlugin,
    DatasetTransformPlugin,
    DatasetTransformResult,
    DatasetTransformSpec,
    PluginContext,
    PluginMetadata,
    ServicePlugin,
    ServiceStatus,
    TUIMenuContribution,
)
from clirobot.doctor.checker import CheckItem
from clirobot.tui.menu import MenuItem
from clirobot.ui.console import console, print_error, print_info, print_success


class DatasetVisualizerPlugin(ServicePlugin, DatasetTransformPlugin):
    """Adapter for lerobot-dataset-visualizer web application and FastAPI annotation service."""

    metadata = PluginMetadata(
        id="dataset-visualizer",
        name="LeRobot Dataset Visualizer & Annotation Studio",
        version="0.1.0",
        description="Interactive 3D URDF visualizer, action insights, and v3.1 language/VQA annotation backend.",
        category="visualization",
        author="SinfonIA UniAndes & LeRobot Community",
    )

    def __init__(self):
        self._backend_proc: Optional[subprocess.Popen] = None
        self._frontend_proc: Optional[subprocess.Popen] = None

    def _resolve_repo(self) -> Optional[Path]:
        """Locate sibling lerobot-dataset-visualizer directory if present."""
        clirobot_dir = Path(__file__).resolve().parent.parent.parent.parent
        workspace_root = clirobot_dir.parent
        candidate = workspace_root / "lerobot-dataset-visualizer"
        if candidate.is_dir():
            return candidate
        return None

    def is_available(self) -> tuple[bool, str]:
        repo = self._resolve_repo()
        if repo and (repo / "package.json").is_file():
            return True, f"Found in workspace ({repo.name})"
        return False, "lerobot-dataset-visualizer directory not found"

    # ==========================================================================
    # Capability: ServicePlugin
    # ==========================================================================

    def start_service(
        self,
        ctx: PluginContext,
        foreground: bool = True,
        frontend_port: int = 3000,
        backend_port: int = 7861,
        use_docker: bool = False,
        **kwargs: Any,
    ) -> int:
        repo = self._resolve_repo()
        if not repo:
            print_error("Cannot start visualizer: lerobot-dataset-visualizer directory not found.")
            return 1

        if use_docker:
            ctx.console.print("[bold cyan]Launching visualizer via Docker Compose...[/bold cyan]")
            cmd = ["docker", "compose", "up"]
            try:
                proc = subprocess.Popen(cmd, cwd=str(repo))
                if foreground:
                    proc.wait()
                    return proc.returncode
                return 0
            except Exception as e:
                print_error(f"Failed to start Docker Compose: {e}")
                return 1

        # Check prerequisites
        backend_dir = repo / "backend"
        bun_bin = shutil.which("bun") or shutil.which("npm")
        if not bun_bin:
            print_error("Neither 'bun' nor 'npm' found in PATH. Install Bun: curl -fsSL https://bun.sh/install | bash")
            return 1

        env = os.environ.copy()
        env["NEXT_PUBLIC_ANNOTATE_BACKEND_URL"] = f"http://127.0.0.1:{backend_port}"
        env["PORT"] = str(frontend_port)

        ctx.console.print(
            Panel(
                f"[bold green]Starting LeRobot Dataset Visualizer Services[/bold green]\n\n"
                f"  • Frontend: [bold cyan]http://localhost:{frontend_port}[/bold cyan]\n"
                f"  • Backend:  [bold cyan]http://127.0.0.1:{backend_port}[/bold cyan]\n\n"
                f"[dim]Press Ctrl+C to stop both services.[/dim]",
                title="[bold blue]🌐 LeRobot Dataset Visualizer[/bold blue]",
                border_style="bright_blue",
                padding=(1, 2),
            )
        )

        try:
            # 1. Start FastAPI backend
            backend_cmd = [
                sys.executable,
                "-m",
                "uvicorn",
                "app:app",
                "--port",
                str(backend_port),
                "--reload",
            ]
            self._backend_proc = subprocess.Popen(backend_cmd, cwd=str(backend_dir))

            time.sleep(1)

            # 2. Start Next.js frontend
            frontend_cmd = [bun_bin, "run", "dev"] if "bun" in bun_bin else [bun_bin, "run", "dev"]
            self._frontend_proc = subprocess.Popen(frontend_cmd, cwd=str(repo), env=env)

            if foreground:
                self._frontend_proc.wait()
            return 0
        except KeyboardInterrupt:
            ctx.console.print("\n[yellow]Stopping visualizer services...[/yellow]")
            self.stop_service(ctx)
            return 0
        except Exception as e:
            print_error(f"Error starting visualizer: {e}")
            self.stop_service(ctx)
            return 1

    def stop_service(self, ctx: PluginContext) -> bool:
        stopped = False
        if self._frontend_proc and self._frontend_proc.poll() is None:
            self._frontend_proc.terminate()
            stopped = True
        if self._backend_proc and self._backend_proc.poll() is None:
            self._backend_proc.terminate()
            stopped = True
        return stopped

    def get_service_status(self, ctx: PluginContext) -> ServiceStatus:
        endpoints = {}
        backend_ok = False
        frontend_ok = False

        # Probe backend health
        try:
            req = urllib.request.Request("http://127.0.0.1:7861/api/health", headers={"User-Agent": "CLIrobot"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    backend_ok = True
                    endpoints["backend"] = "http://127.0.0.1:7861"
        except Exception:
            pass

        # Probe frontend
        try:
            req = urllib.request.Request("http://localhost:3000", headers={"User-Agent": "CLIrobot"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    frontend_ok = True
                    endpoints["frontend"] = "http://localhost:3000"
        except Exception:
            pass

        running = backend_ok or frontend_ok
        detail = "Running (Online)" if (backend_ok and frontend_ok) else ("Partial (Backend only)" if backend_ok else ("Partial (Frontend only)" if frontend_ok else "Stopped"))
        return ServiceStatus(running=running, endpoints=endpoints, detail=detail)

    # ==========================================================================
    # REST Client Methods
    # ==========================================================================

    def load_dataset(self, repo_id_or_path: str, backend_url: str = "http://127.0.0.1:7861") -> dict[str, Any]:
        """Preload a dataset into the visualizer backend."""
        payload = json.dumps({"repo_id": repo_id_or_path}).encode("utf-8")
        req = urllib.request.Request(
            f"{backend_url}/api/dataset/load",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def export_annotations(
        self,
        repo_id: str,
        output_dir: Optional[str] = None,
        backend_url: str = "http://127.0.0.1:7861",
    ) -> dict[str, Any]:
        """Rewrite dataset Parquet shards with v3.1 language columns."""
        body: dict[str, Any] = {"repo_id": repo_id}
        if output_dir:
            body["output_dir"] = output_dir
        req = urllib.request.Request(
            f"{backend_url}/api/export",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def push_to_hub(
        self,
        repo_id: str,
        hf_token: Optional[str] = None,
        backend_url: str = "http://127.0.0.1:7861",
    ) -> dict[str, Any]:
        """Push annotated dataset to Hugging Face Hub via visualizer backend."""
        token = hf_token or os.environ.get("HF_TOKEN", "")
        req = urllib.request.Request(
            f"{backend_url}/api/push_to_hub",
            data=json.dumps({"repo_id": repo_id, "hf_token": token}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60.0) as resp:
            return json.loads(resp.read().decode("utf-8"))

    # ==========================================================================
    # Capability: DatasetTransformPlugin (Annotation Export)
    # ==========================================================================

    def get_transforms(self) -> list[DatasetTransformSpec]:
        return [
            DatasetTransformSpec(
                id="export-v3-language",
                name="Export v3.1 Language Annotations",
                description="Rewrite Parquet shards with language_persistent and language_events columns via visualizer backend.",
                icon="🏷️",
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
        if transform_id != "export-v3-language":
            raise ValueError(f"Unknown transform: {transform_id}")

        if dry_run:
            ctx.console.print(
                Panel(
                    f"Will export v3.1 language columns from visualizer backend for repo: {input_repo}\n"
                    f"Destination: {output_dir or 'Default export path'}\n"
                    f"Push to Hub: {push_to_hub}",
                    title="Export v3.1 Language Dry Run",
                    border_style="yellow",
                )
            )
            return DatasetTransformResult(
                transform_id="export-v3-language",
                success=True,
                input_repo_or_path=input_repo,
                output_path=output_dir,
                metrics={"dry_run": True},
            )

        try:
            res = self.export_annotations(input_repo, output_dir=output_dir)
            if push_to_hub:
                self.push_to_hub(output_repo or input_repo)
            return DatasetTransformResult(
                transform_id="export-v3-language",
                success=True,
                input_repo_or_path=input_repo,
                output_path=res.get("export_dir", output_dir),
                output_repo_id=output_repo,
                metrics=res,
            )
        except Exception as e:
            return DatasetTransformResult(
                transform_id="export-v3-language",
                success=False,
                input_repo_or_path=input_repo,
                warnings=[str(e)],
            )

    # ==========================================================================
    # CLI Commands
    # ==========================================================================

    def register_cli(self, root_app: typer.Typer, sub_apps: dict[str, typer.Typer]) -> None:
        viz_app = typer.Typer(
            name="visualizer",
            help="Web visualizer & FastAPI annotation studio (lerobot-dataset-visualizer).",
            no_args_is_help=False,
        )

        @viz_app.command("start")
        def start_cmd(
            port: int = typer.Option(3000, "--port", "-p", help="Frontend web port"),
            backend_port: int = typer.Option(7861, "--backend-port", "-b", help="FastAPI backend port"),
            docker: bool = typer.Option(False, "--docker", "-d", help="Use Docker Compose"),
        ):
            """Start both the Next.js visualizer and FastAPI annotation backend."""
            from clirobot.config.manager import ConfigManager
            from clirobot.integration.runner import CommandRunner

            ctx = PluginContext(ConfigManager(), CommandRunner(), console)
            self.start_service(ctx, foreground=True, frontend_port=port, backend_port=backend_port, use_docker=docker)

        @viz_app.command("status")
        def status_cmd():
            """Query health status of visualizer frontend and backend."""
            from clirobot.config.manager import ConfigManager
            from clirobot.integration.runner import CommandRunner

            ctx = PluginContext(ConfigManager(), CommandRunner(), console)
            stat = self.get_service_status(ctx)
            color = "green" if stat.running else "yellow"
            console.print(f"\n[bold cyan]Visualizer Status:[/bold cyan] [{color}]{stat.detail}[/{color}]")
            for name, url in stat.endpoints.items():
                console.print(f"  • {name.capitalize()}: [bold underline]{url}[/bold underline]")
            console.print()

        @viz_app.command("load")
        def load_cmd(
            repo_id: Optional[str] = typer.Option(None, "--repo-id", "-r", help="Dataset repo ID or local path"),
        ):
            """Preload a dataset into the visualizer annotation backend."""
            from clirobot.config.manager import ConfigManager

            mgr = ConfigManager()
            target_repo = repo_id or mgr.get_active_profile().dataset_repo_id
            try:
                res = self.load_dataset(target_repo)
                print_success(f"Loaded dataset '{target_repo}' into visualizer backend: {res}")
            except Exception as e:
                print_error(f"Failed to load dataset: {e}\nIs the backend running? (clirobot visualizer start)")

        @viz_app.command("push-hub")
        def push_hub_cmd(
            repo_id: Optional[str] = typer.Option(None, "--repo-id", "-r", help="Dataset repo ID"),
            token: Optional[str] = typer.Option(None, "--token", "-t", help="Hugging Face API token"),
        ):
            """Export annotations and push dataset to Hugging Face Hub via visualizer backend."""
            from clirobot.config.manager import ConfigManager

            mgr = ConfigManager()
            target_repo = repo_id or mgr.get_active_profile().dataset_repo_id
            try:
                res = self.push_to_hub(target_repo, hf_token=token)
                print_success(f"Pushed annotations to Hugging Face Hub: {res}")
            except Exception as e:
                print_error(f"Failed to push annotations: {e}")

        root_app.add_typer(viz_app, name="visualizer", help="Web visualizer & annotation studio")
        root_app.add_typer(viz_app, name="viz-web", help="Alias for 'visualizer'")

    # ==========================================================================
    # TUI Contributions
    # ==========================================================================

    def get_tui_contributions(self, ctx: PluginContext) -> list[TUIMenuContribution]:
        return [
            TUIMenuContribution(
                target_menu="datasets",
                item=MenuItem(
                    id="launch_web_visualizer",
                    label="Launch Web Visualizer & Annotation Studio",
                    icon="🌐",
                    description="Launch Next.js interactive URDF/action visualizer (port 3000) and annotation service (port 7861).",
                ),
                handler=lambda c: self.start_service(c, foreground=True),
                order=5,
            ),
            TUIMenuContribution(
                target_menu="datasets",
                item=MenuItem(
                    id="sync_web_annotations_hub",
                    label="Sync Web Annotations to HF Hub",
                    icon="☁️",
                    description="Export and publish latest web annotations (subtasks, VQA) to Hugging Face Hub.",
                ),
                handler=self._tui_push_hub,
                order=6,
            ),
        ]

    def _tui_push_hub(self, ctx: PluginContext) -> None:
        from rich.prompt import Prompt

        repo = Prompt.ask("Dataset repo ID to sync", default=ctx.active_profile.dataset_repo_id)
        try:
            res = self.push_to_hub(repo)
            print_success(f"Synchronized web annotations to Hub: {res}")
        except Exception as e:
            print_error(f"Hub sync error: {e}\nEnsure visualizer backend is running (clirobot visualizer start).")

    # ==========================================================================
    # Doctor Checks
    # ==========================================================================

    def run_doctor_checks(self, ctx: PluginContext) -> list[CheckItem]:
        checks = []
        is_avail, reason = self.is_available()
        checks.append(
            CheckItem(
                category="Visualizer",
                name="Visualizer Directory",
                status="PASS" if is_avail else "WARN",
                detail=reason,
                recommendation="" if is_avail else "Clone lerobot-dataset-visualizer into workspace",
            )
        )

        bun_found = bool(shutil.which("bun"))
        checks.append(
            CheckItem(
                category="Visualizer",
                name="Bun Package Manager",
                status="PASS" if bun_found else "WARN",
                detail="Installed" if bun_found else "bun not found in PATH",
                recommendation="" if bun_found else "Install bun: curl -fsSL https://bun.sh/install | bash",
            )
        )

        stat = self.get_service_status(ctx)
        checks.append(
            CheckItem(
                category="Visualizer",
                name="Visualizer Services Status",
                status="PASS" if stat.running else "WARN",
                detail=stat.detail,
                recommendation="" if stat.running else "Run 'clirobot visualizer start' to launch web interface",
            )
        )

        return checks
