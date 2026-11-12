"""Isolated Docker sandbox for verifying findings against repo tests/linters."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SandboxResult:
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    method: str


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    result = subprocess.run(["docker", "info"], capture_output=True, check=False)
    return result.returncode == 0


def run_in_sandbox(
    repo_path: str,
    command: list[str],
    *,
    method: str = "sandbox",
    workdir: str = "/workspace",
    network_disabled: bool = True,
) -> SandboxResult:
    """
    Execute a command against a read-only copy of the repo inside a constrained container.
    Never mounts application secrets. Network is disabled by default.
    """
    import time

    started = time.time()
    if not docker_available():
        return SandboxResult(
            success=False,
            exit_code=-1,
            stdout="",
            stderr="Docker unavailable for sandbox execution",
            duration_ms=0,
            method=method,
        )

    src = Path(repo_path)
    if not src.exists():
        return SandboxResult(
            False, -1, "", f"Repo path missing: {repo_path}", 0, method
        )

    tmp = Path(tempfile.mkdtemp(prefix="spider-sandbox-"))
    try:
        # Copy tree excluding .git large objects optionally — keep .git for some tools
        shutil.copytree(src, tmp / "repo", dirs_exist_ok=True, ignore=shutil.ignore_patterns(".venv", "node_modules"))

        image = settings.sandbox_image
        # Fallback to python slim if custom image missing
        inspect = subprocess.run(["docker", "image", "inspect", image], capture_output=True)
        if inspect.returncode != 0:
            image = "python:3.12-slim"

        docker_cmd = [
            "docker", "run", "--rm",
            "--network", "none" if network_disabled else "bridge",
            "--memory", settings.sandbox_memory_limit,
            "--cpus", str(settings.sandbox_cpu_limit),
            "--pids-limit", "256",
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "-v", f"{tmp / 'repo'}:{workdir}:ro",
            "-w", workdir,
            "--user", "65534:65534",
            image,
            *command,
        ]
        result = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=settings.sandbox_timeout_seconds,
            check=False,
        )
        duration_ms = int((time.time() - started) * 1000)
        return SandboxResult(
            success=result.returncode == 0,
            exit_code=result.returncode,
            stdout=result.stdout[-20000:],
            stderr=result.stderr[-20000:],
            duration_ms=duration_ms,
            method=method,
        )
    except subprocess.TimeoutExpired:
        return SandboxResult(False, -1, "", "Sandbox timed out", int((time.time() - started) * 1000), method)
    except Exception as exc:
        logger.exception("sandbox_failed")
        return SandboxResult(False, -1, "", str(exc), int((time.time() - started) * 1000), method)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def detect_project_commands(repo_path: str) -> dict[str, list[str]]:
    root = Path(repo_path)
    cmds: dict[str, list[str]] = {}
    if (root / "pyproject.toml").exists() or (root / "pytest.ini").exists() or list(root.glob("**/test_*.py")):
        cmds["unit_test"] = ["python", "-m", "pytest", "-q", "--maxfail=5"]
        cmds["lint"] = ["python", "-m", "compileall", "-q", "."]
    if (root / "package.json").exists():
        cmds.setdefault("unit_test", ["npm", "test", "--", "--watchAll=false"])
    if (root / "Cargo.toml").exists():
        cmds["unit_test"] = ["cargo", "test", "--", "--quiet"]
    if (root / "go.mod").exists():
        cmds["unit_test"] = ["go", "test", "./..."]
    return cmds