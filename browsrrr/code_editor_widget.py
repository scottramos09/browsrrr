from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from .code_runner import CodeRunner


class CodeEditorWidget(QWidget):
    def __init__(self, code_runner: CodeRunner) -> None:
        super().__init__()
        self._code_runner = code_runner

        layout = QVBoxLayout(self)

        self._editor = QPlainTextEdit(self)
        self._editor.setPlaceholderText("# Python code")

        self._output = QPlainTextEdit(self)
        self._output.setReadOnly(True)

        run_button = QPushButton("Run Python", self)
        run_button.clicked.connect(self._run_code)

        layout.addWidget(QLabel("In-browser local coding", self))
        layout.addWidget(self._editor)
        layout.addWidget(run_button)
        layout.addWidget(self._output)

    def _run_code(self) -> None:
        result = self._code_runner.run_python(self._editor.toPlainText())
        self._output.setPlainText(result.output)