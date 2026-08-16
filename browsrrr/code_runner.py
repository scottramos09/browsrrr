from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from subprocess import TimeoutExpired, run
from sys import executable
from tempfile import NamedTemporaryFile
from typing import Protocol


@dataclass
class CodeRunResult:
    stdout: str
    stderr: str
    returncode: int

    @property
    def output(self) -> str:
        parts = [part for part in (self.stdout, self.stderr) if part]
        return "\n".join(parts) if parts else "No output."


class CodeRunner(Protocol):
    def run_python(self, code: str) -> CodeRunResult:
        ...


class SubprocessCodeRunner:
    def __init__(self, timeout_seconds: int = 10) -> None:
        self._timeout_seconds = timeout_seconds

    def run_python(self, code: str) -> CodeRunResult:
        script_path = self._write_temporary_script(code)

        try:
            completed = run(
                [executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
            )
            return CodeRunResult(completed.stdout, completed.stderr, completed.returncode)
        except TimeoutExpired as error:
            stdout = self._to_text(error.stdout)
            return CodeRunResult(stdout, f"Timed out after {self._timeout_seconds} seconds.", 1)
        finally:
            script_path.unlink(missing_ok=True)

    @staticmethod
    def _write_temporary_script(code: str) -> Path:
        with NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as file:
            file.write(code)
            return Path(file.name)

    @staticmethod
    def _to_text(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)