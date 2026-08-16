from PySide6.QtCore import QThread, Signal

from .ai_service import AiAgent


class AiWorker(QThread):
    result_ready = Signal(str)

    def __init__(self, agent: AiAgent, prompt: str) -> None:
        super().__init__()
        self._agent = agent
        self._prompt = prompt

    def run(self) -> None:
        try:
            result = self._agent.complete(self._prompt)
        except Exception as error:  # surface failures in-panel, never crash UI
            result = f"AI error: {error}"
        self.result_ready.emit(result)