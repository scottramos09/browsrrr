import shutil
import subprocess
import webbrowser


def is_ollama_installed() -> bool:
    return shutil.which("ollama") is not None


def install_ollama() -> None:
    """Attempts silent install via winget, falls back to opening download page."""
    try:
        subprocess.Popen(
            ["winget", "install", "Ollama.Ollama", "--accept-source-agreements", "--accept-package-agreements"],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (OSError, FileNotFoundError):
        webbrowser.open("https://ollama.com/download")