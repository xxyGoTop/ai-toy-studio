from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings


@dataclass
class BlenderResult:
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    data: dict | list | None = None


class BlenderRunner:
    def __init__(self, settings: Settings):
        self.settings = settings

    def run_script(self, script_name: str, args: dict[str, str | float | int | bool]) -> BlenderResult:
        blender = Path(self.settings.blender_executable)
        if not blender.exists():
            return BlenderResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Blender executable not found: {blender}",
                data=None,
            )

        script_path = self.settings.blender_scripts_dir / script_name
        if not script_path.exists():
            return BlenderResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Script not found: {script_path}",
                data=None,
            )

        command = [
            str(blender),
            "-b",
            "--python",
            str(script_path),
            "--",
        ]
        for key, value in args.items():
            command.append(f"--{key}")
            if isinstance(value, bool):
                command.append("1" if value else "0")
            else:
                command.append(str(value))

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.settings.blender_timeout_seconds,
                check=False,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            return BlenderResult(
                success=False,
                exit_code=-1,
                stdout=exc.stdout or "",
                stderr=f"Blender timed out after {self.settings.blender_timeout_seconds}s",
                data=None,
            )

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        payload = self._extract_json(stdout)
        success = completed.returncode == 0 and not (
            isinstance(payload, dict) and payload.get("success") is False
        )
        return BlenderResult(
            success=success,
            exit_code=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            data=payload,
        )

    @staticmethod
    def _extract_json(stdout: str) -> dict | list | None:
        if not stdout:
            return None
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        for line in reversed(lines):
            if line.startswith("{") or line.startswith("["):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        return None
