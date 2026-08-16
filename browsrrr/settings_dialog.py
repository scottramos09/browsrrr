from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout,
)

from .config import Settings
from .ollama import install_ollama, is_ollama_installed


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("BrowsRrr Settings")
        self.resize(400, 300)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._ai_mode = QComboBox()
        self._ai_mode.addItems(["echo", "local", "api"])
        self._ai_mode.setCurrentText(settings.ai_mode)

        self._local_cmd = QLineEdit(settings.ai_local_command)
        self._api_url = QLineEdit(settings.ai_api_url)
        self._api_key = QLineEdit(settings.ai_api_key)
        self._api_key.setEchoMode(QLineEdit.Password)
        self._model = QLineEdit(settings.ai_model)

        status = "Installed" if is_ollama_installed() else "Not Found"
        self._ollama_btn = QPushButton(f"Install Ollama ({status})")
        self._ollama_btn.clicked.connect(self._install_ollama)

        form.addRow("AI Mode:", self._ai_mode)
        form.addRow("Local Command:", self._local_cmd)
        form.addRow("API URL:", self._api_url)
        form.addRow("API Key:", self._api_key)
        form.addRow("Model:", self._model)
        form.addRow(self._ollama_btn)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def _install_ollama(self) -> None:
        install_ollama()
        self._ollama_btn.setText("Installing... (check winget)")

    def get_settings(self) -> Settings:
        return Settings(
            ai_mode=self._ai_mode.currentText(),
            ai_local_command=self._local_cmd.text(),
            ai_api_url=self._api_url.text(),
            ai_api_key=self._api_key.text(),
            ai_model=self._model.text(),
        )