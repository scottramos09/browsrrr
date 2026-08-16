import sys

from PySide6.QtWidgets import QApplication

from .ai_service import build_ai_agent
from .code_runner import SubprocessCodeRunner
from .config import default_settings_path, load_settings
from .session import default_session_path
from .win32_embedder import create_app_embedder
from .workspace_window import WorkspaceWindow


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("BrowsRrr")

    # Global Dark Mode Stylesheet
    app.setStyleSheet("""
        QMainWindow { background: #202124; }
        QWidget { background: #202124; color: #E8EAED; }
        QLineEdit { background: #303134; border: 1px solid #5F6368; padding: 4px; color: #E8EAED; }
        QPushButton { background: #303134; border: 1px solid #5F6368; padding: 4px 8px; color: #E8EAED; }
        QPushButton:hover { background: #3C4043; }
        QPlainTextEdit { background: #2b2b2b; color: #E8EAED; border: 1px solid #5F6368; }
    """)

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