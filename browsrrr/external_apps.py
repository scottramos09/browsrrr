from __future__ import annotations

import os
import shlex
import subprocess


class ExternalAppError(RuntimeError):
    pass


class SubprocessExternalAppLauncher:
    def launch(self, command: str) -> str:
        command = command.strip()
        if not command:
            raise ExternalAppError("Command is required.")

        try:
            if os.name == "nt":
                subprocess.Popen(command, shell=True)
                return f"Launched: {command}"

            args = shlex.split(command)
            subprocess.Popen(args)
            return f"Launched: {args[0]}"
        except FileNotFoundError as error:
            raise ExternalAppError(f"Application not found: {command}") from error
        except OSError as error:
            raise ExternalAppError(f"Could not launch application: {error}") from error