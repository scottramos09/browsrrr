from __future__ import annotations

import json
import subprocess
from typing import Protocol
from urllib.request import Request, urlopen

from .config import Settings


class AiAgentError(RuntimeError):
    pass


class AiAgent(Protocol):
    def complete(self, prompt: str) -> str:
        ...


class EchoAiAgent:
    def complete(self, prompt: str) -> str:
        prompt = prompt.strip()
        return f"BrowsRrr AI stub: {prompt}" if prompt else "Enter a prompt first."


class LocalCliAgent:
    """Runs a local CLI that reads the prompt from stdin and writes the answer to stdout."""

    def __init__(self, command: str, timeout_seconds: int = 120) -> None:
        self._command = command
        self._timeout_seconds = timeout_seconds

    def complete(self, prompt: str) -> str:
        if not self._command.strip():
            raise AiAgentError("ai_local_command is not configured.")
        try:
            completed = subprocess.run(
                self._command,
                input=prompt,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise AiAgentError(f"Local AI failed: {error}") from error
        output = (completed.stdout or completed.stderr).strip()
        return output or "No response from local AI."


class OpenAiCompatibleAgent:
    def __init__(self, url: str, api_key: str, model: str, timeout_seconds: int = 60) -> None:
        self._url = url
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    def complete(self, prompt: str) -> str:
        if not self._api_key:
            raise AiAgentError("ai_api_key is not configured.")
        body = json.dumps(
            {"model": self._model, "messages": [{"role": "user", "content": prompt}]}
        ).encode("utf-8")
        request = Request(
            self._url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError) as error:
            raise AiAgentError(f"AI API request failed: {error}") from error
        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise AiAgentError(f"Unexpected AI API response: {payload}") from error


def build_ai_agent(settings: Settings) -> AiAgent:
    if settings.ai_mode == "local":
        return LocalCliAgent(settings.ai_local_command)
    if settings.ai_mode == "api":
        return OpenAiCompatibleAgent(settings.ai_api_url, settings.ai_api_key, settings.ai_model)
    return EchoAiAgent()