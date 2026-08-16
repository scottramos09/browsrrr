import json
import sys

from browsrrr.ai_service import (
    EchoAiAgent, LocalCliAgent, OpenAiCompatibleAgent, build_ai_agent,
)
from browsrrr.config import Settings


def test_echo_agent():
    assert "hello" in EchoAiAgent().complete("hello")


def test_local_cli_agent_reads_stdin():
    command = f'"{sys.executable}" -c "import sys; print(sys.stdin.read().strip().upper())"'

    assert LocalCliAgent(command, timeout_seconds=30).complete("ok") == "OK"


def test_openai_agent_parses_response(monkeypatch):
    import browsrrr.ai_service as ai_service

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self):
            return json.dumps({"choices": [{"message": {"content": "hi"}}]}).encode()

    monkeypatch.setattr(ai_service, "urlopen", lambda *a, **k: FakeResponse())
    agent = OpenAiCompatibleAgent("https://example/v1/chat/completions", "key", "model")

    assert agent.complete("hello") == "hi"


def test_factory_modes():
    assert isinstance(build_ai_agent(Settings(ai_mode="echo")), EchoAiAgent)
    assert isinstance(build_ai_agent(Settings(ai_mode="local")), LocalCliAgent)
    assert isinstance(build_ai_agent(Settings(ai_mode="api")), OpenAiCompatibleAgent)