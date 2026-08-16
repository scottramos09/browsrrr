import shutil

from browsrrr.ollama import is_ollama_installed


def test_is_ollama_installed_matches_path(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/ollama" if x == "ollama" else None)
    assert is_ollama_installed() is True

    monkeypatch.setattr(shutil, "which", lambda x: None)
    assert is_ollama_installed() is False