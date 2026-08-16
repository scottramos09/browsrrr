from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from .ai_service import AiAgent
from .ai_worker import AiWorker


class AiPanelWidget(QWidget):
    def __init__(self, agent: AiAgent) -> None:
        super().__init__()
        self._agent = agent
        self._worker: AiWorker | None = None

        layout = QVBoxLayout(self)
        self._prompt = QPlainTextEdit()
        self._prompt.setPlaceholderText("Ask the AI agent...")

        self._output = QLabel("AI output appears here.")
        self._output.setWordWrap(True)

        ask = QPushButton("Ask AI")
        ask.clicked.connect(self._ask)

        layout.addWidget(self._prompt)
        layout.addWidget(ask)
        layout.addWidget(self._output)

    def _ask(self) -> None:
        prompt = self._prompt.toPlainText()
        if not prompt.strip():
            return
        if self._worker is not None and self._worker.isRunning():
            return
        self._output.setText("Thinking...")
        self._worker = AiWorker(self._agent, prompt)
        self._worker.result_ready.connect(self._output.setText)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()