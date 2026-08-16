from browsrrr.app_catalog import AppEntry, load_entries, record_recent, save_entries


def test_round_trip(tmp_path):
    path = tmp_path / "apps.json"
    entries = [AppEntry("Game", "C:\\Games\\game.exe")]

    save_entries(path, entries)

    assert load_entries(path) == entries


def test_record_recent_dedups_and_caps(tmp_path):
    path = tmp_path / "recent.json"
    for i in range(15):
        record_recent(f"C:\\app{i}.exe", file=path)
    record_recent("C:\\app7.exe", file=path)

    recents = load_entries(path)

    assert recents[0].path == "C:\\app7.exe"
    assert len(recents) == 12
    assert sum(1 for e in recents if e.path == "C:\\app7.exe") == 1