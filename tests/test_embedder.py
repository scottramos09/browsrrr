import os

import pytest

from browsrrr.win32_embedder import (
    ExternalAppError, NullAppEmbedder, Win32AppEmbedder, create_app_embedder,
)


def test_factory_matches_platform():
    embedder = create_app_embedder()

    if os.name == "nt":
        assert isinstance(embedder, Win32AppEmbedder)
    else:
        assert isinstance(embedder, NullAppEmbedder)


def test_null_embedder_rejects_launch():
    with pytest.raises(ExternalAppError):
        NullAppEmbedder().launch("notepad.exe")


@pytest.mark.skipif(os.name != "nt", reason="Windows only")
def test_launch_and_find_window():
    embedder = Win32AppEmbedder()
    process = embedder.launch("notepad.exe")
    try:
        assert embedder.find_main_hwnd(process.pid, timeout_seconds=10)
    finally:
        process.terminate()