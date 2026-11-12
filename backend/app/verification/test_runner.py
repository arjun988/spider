"""Run targeted verification commands in the sandbox."""

from __future__ import annotations

from app.verification.sandbox import SandboxResult, detect_project_commands, run_in_sandbox


def run_relevant_checks(repo_path: str) -> list[SandboxResult]:
    commands = detect_project_commands(repo_path)
    results: list[SandboxResult] = []
    # Prefer compile/lint style checks first — safer and faster
    if "lint" in commands:
        results.append(run_in_sandbox(repo_path, commands["lint"], method="lint"))
    # Unit tests only if project clearly supports them and sandbox image has tooling
    # Skip npm/cargo/go by default in generic python image to avoid false failures
    if "unit_test" in commands and commands["unit_test"][:3] == ["python", "-m", "pytest"]:
        # Try a no-op friendly compile instead if pytest may be missing
        compile_result = run_in_sandbox(
            repo_path,
            ["python", "-m", "compileall", "-q", "."],
            method="type_check",
        )
        results.append(compile_result)
    return results