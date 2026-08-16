import os
import sys

from PySide6.QtWidgets import QApplication

from .ai_service import build_ai_agent
from .code_runner import SubprocessCodeRunner
from .config import default_settings_path, load_settings
from .session import default_session_path
from .win32_embedder import create_app_embedder
from .workspace_window import WorkspaceWindow


def run() -> int:
    com_owned = False
    if os.name == "nt":
        from . import win32_api as api

        # Shell icon/PIDL calls (SHParseDisplayName, SHGetFileInfo) require COM
        # on the painting thread. Initialize once, before any widget paints.
        com_owned = api.ole32.CoInitializeEx(None, 2) == 0  # COINIT_APARTMENTTHREADED

    try:
        app = QApplication(sys.argv)
        app.setApplicationName("BrowsRrr")
        app.setStyleSheet(
            "QMainWindow { background: #202124; } "
            "QWidget { background: #202124; color: #E8EAED; } "
            "QLineEdit { background: #303134; border: 1px solid #5F6368; padding: 4px; color: #E8EAED; } "
            "QPushButton { background: #303134; border: 1px solid #5F6368; padding: 4px 8px; color: #E8EAED; } "
            "QPushButton:hover { background: #3C4043; } "
            "QPlainTextEdit { background: #2b2b2b; color: #E8EAED; border: 1px solid #5F6368; }"
        )

        settings_path = default_settings_path()

        window = WorkspaceWindow(
            ai_agent=build_ai_agent(load_settings(settings_path)),
            embedder=create_app_embedder(),
            code_runner=SubprocessCodeRunner(),
            settings=load_settings(settings_path),
            settings_path=settings_path,
            session_path=default_session_path(),
        )
        window.show()
        return app.exec()
    finally:
        if com_owned:
            from . import win32_api as api

            api.ole32.CoUninitialize()