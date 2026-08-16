from browsrrr.config import Settings, load_settings, save_settings


def test_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(ai_mode="api"), path)

    assert load_settings(path).ai_mode == "api"


def test_missing_file_returns_defaults(tmp_path):
    assert load_settings(tmp_path / "nope.json").ai_mode == "echo"


def test_unknown_keys_ignored(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"ai_mode": "local", "junk": 1}', encoding="utf-8")

    assert load_settings(path).ai_mode == "local"