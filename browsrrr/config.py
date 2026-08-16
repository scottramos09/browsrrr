from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path


@dataclass
class Settings:
    ai_mode: str = "echo"
    ai_local_command: str = ""
    ai_api_url: str = "https://api.openai.com/v1/chat/completions"
    ai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"
    last_embed_command: str = ""


def default_settings_path() -> Path:
    return Path.home() / ".browsrrr" / "settings.json"


def load_settings(path: Path) -> Settings:
    if not path.exists():
        return Settings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return Settings()
    known = {field.name for field in fields(Settings)}
    return Settings(**{k: v for k, v in data.items() if k in known})


def save_settings(settings: Settings, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")