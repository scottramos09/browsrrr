from browsrrr.session import load_session, save_session


def test_round_trip(tmp_path):
    path = tmp_path / "session.json"
    data = {"geometry": [0, 0, 800, 600], "tabs": [{"url": "https://test.com"}]}
    save_session(path, data)

    loaded = load_session(path)

    assert loaded["geometry"] == [0, 0, 800, 600]
    assert loaded["tabs"][0]["url"] == "https://test.com"


def test_missing_file_returns_empty_dict(tmp_path):
    assert load_session(tmp_path / "nope.json") == {}