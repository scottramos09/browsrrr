from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

TITLE_BAR_HEIGHT = 36
CONTROLS_WIDTH = 96
CONTROLS_HEIGHT = 26


class WindowControlsWidget(QWidget):
    """Floating minimize/maximize/close cluster for monitors where the title bar is invisible."""

    def __init__(
        self,
        parent: QWidget,
        on_minimize: Callable[[], None],
        on_maximize: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(CONTROLS_WIDTH, CONTROLS_HEIGHT)
        self.setStyleSheet(
            "WindowControlsWidget { background: #1e1e1e; border: 1px solid #444; } "
            "QPushButton { color: #eee; background: transparent; border: none; }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for text, slot, hover in (
            ("—", on_minimize, "QPushButton:hover { background: #444; }"),
            ("□", on_maximize, "QPushButton:hover { background: #444; }"),
            ("×", on_close, "QPushButton:hover { background: #e81123; }"),
        ):
            button = QPushButton(text)
            button.setFixedSize(32, CONTROLS_HEIGHT)
            button.setStyleSheet(hover)
            button.clicked.connect(slot)
            layout.addWidget(button)


class TitleBar(QWidget):
    def __init__(
        self,
        parent: QWidget,
        on_minimize: Callable[[], None],
        on_maximize: Callable[[], None],
        on_close: Callable[[], None],
        actions: list[tuple[str, Callable[[], None]]],
    ) -> None:
        super().__init__(parent)
        self.setFixedHeight(TITLE_BAR_HEIGHT)
        self.setStyleSheet("TitleBar { background: #1e1e1e; } QLabel { color: #eee; }")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 4, 0)
        layout.setSpacing(4)
        layout.addWidget(QLabel("BrowsRrr"))

        for text, slot in actions:
            button = QPushButton(text)
            button.setFixedHeight(26)
            button.clicked.connect(slot)
            layout.addWidget(button)

        layout.addStretch(1)
        for text, slot in (("-", on_minimize), ("□", on_maximize), ("×", on_close)):
            button = QPushButton(text)
            button.setFixedSize(32, 26)
            button.clicked.connect(slot)
            layout.addWidget(button)