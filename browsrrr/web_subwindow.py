from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget

from .urls import normalize_url


class WebSubWindowContent(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._view = QWebEngineView(self)

        nav = QWidget(self)
        nav.setFixedHeight(30)
        nav.setStyleSheet("background: #333;")
        row = QHBoxLayout(nav)
        row.setContentsMargins(2, 2, 2, 2)
        row.setSpacing(2)

        self._address = QLineEdit(nav)
        self._address.returnPressed.connect(self._navigate)
        self._view.urlChanged.connect(lambda url: self._address.setText(url.toString()))

        row.addWidget(self._button("←", self._view.back))
        row.addWidget(self._button("→", self._view.forward))
        row.addWidget(self._button("⟳", self._view.reload))
        row.addWidget(self._address, 1)
        row.addWidget(self._button("Go", self._navigate))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(nav)
        layout.addWidget(self._view, 1)

    def _button(self, text: str, slot) -> QPushButton:
        button = QPushButton(text)
        button.setFixedHeight(24)
        button.clicked.connect(slot)
        return button

    def _navigate(self) -> None:
        self._view.setUrl(QUrl(normalize_url(self._address.text())))

    def load(self, url: str) -> None:
        self._view.setUrl(QUrl(normalize_url(url)))

    @property
    def url(self) -> str:
        return self._view.url().toString()