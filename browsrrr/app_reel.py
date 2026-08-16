from __future__ import annotations

from PySide6.QtCore import QRect, QRectF, Qt, QEvent, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QWheelEvent
from PySide6.QtWidgets import QLineEdit, QWidget

from .app_catalog import AppEntry, app_icon

ITEM_H = 84
FILTER_H = 34


class AppReel(QWidget):
    """Photo-reel launcher: recents by default, live Start-Menu-index search while typing."""

    app_chosen = Signal(object)
    dismissed = Signal()

    def __init__(self, recents: list[AppEntry], index: list[AppEntry], parent: QWidget) -> None:
        super().__init__(parent)
        self._recents = list(recents)
        self._index = list(index)
        self._recents_paths = {e.path.lower() for e in self._recents}
        self._entries = list(self._recents)
        self._filter_text = ""
        self._offset = 0.0
        self.setFixedSize(340, 520)
        self.setFocusPolicy(Qt.StrongFocus)

        self._filter = QLineEdit(self)
        self._filter.setPlaceholderText("Search apps...")
        self._filter.setGeometry(12, 10, self.width() - 24, FILTER_H)
        self._filter.setStyleSheet(
            "QLineEdit { background: #303134; color: #E8EAED; border: 1px solid #5F6368; "
            "border-radius: 6px; padding: 4px 8px; }"
        )
        self._filter.installEventFilter(self)
        self._filter.textChanged.connect(self._apply_filter)

    # -- filtering -----------------------------------------------------------

    def _apply_filter(self, text: str) -> None:
        self._filter_text = text
        t = text.strip().lower()
        if t:
            pool = self._recents + [e for e in self._index if e.path.lower() not in self._recents_paths]
            self._entries = [e for e in pool if t in e.name.lower()]
        else:
            self._entries = list(self._recents)
        self._offset = 0.0
        self.update()

    def _clamp_offset(self, value: float) -> float:
        return min(max(0.0, value), max(0.0, len(self._entries) - 1))

    # -- input ---------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:
        if obj is self._filter and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape):
                self.keyPressEvent(event)
                return True
        return super().eventFilter(obj, event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._filter.setFocus()

    def wheelEvent(self, event: QWheelEvent) -> None:
        self._offset = self._clamp_offset(self._offset - event.angleDelta().y() / 240.0)
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Down:
            self._offset = self._clamp_offset(self._offset + 1)
            self.update()
        elif event.key() == Qt.Key_Up:
            self._offset = self._clamp_offset(self._offset - 1)
            self.update()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._choose(int(round(self._offset)))
        elif event.key() == Qt.Key_Escape:
            self.dismissed.emit()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.RightButton:
            self.dismissed.emit()
            return
        if event.button() != Qt.LeftButton:
            return
        if not self._entries:
            return
        top = self._filter.geometry().bottom() + 6
        bottom = self.height() - 6
        center_y = top + (bottom - top) / 2
        index = round(self._offset + (event.position().y() - center_y) / ITEM_H)
        index = min(max(0, index), len(self._entries) - 1)
        if abs(index - self._offset) < 0.5:
            self._choose(index)
        else:
            self._offset = float(index)
            self.update()

    def _choose(self, index: int) -> None:
        if 0 <= index < len(self._entries):
            self.app_chosen.emit(self._entries[index])

    # -- painting ------------------------------------------------------------

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(24, 24, 24, 240))
        p.setPen(QColor(68, 68, 68))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 12, 12)

        top = self._filter.geometry().bottom() + 6
        bottom = self.height() - 6
        p.setClipRect(QRect(2, top, self.width() - 4, bottom - top))

        if not self._entries:
            p.setPen(QColor(200, 200, 200))
            message = (
                "No matches."
                if self._filter_text.strip()
                else "No recent apps yet.\nType to search all apps."
            )
            p.drawText(QRect(0, top, self.width(), bottom - top), Qt.AlignCenter, message)
            return

        center_y = top + (bottom - top) / 2
        for i, entry in enumerate(self._entries):
            d = i - self._offset
            y = center_y + d * ITEM_H
            if y < top - ITEM_H or y > bottom + ITEM_H:
                continue

            scale = max(0.65, 1.0 - 0.18 * min(abs(d), 2.5))
            p.setOpacity(max(0.25, 1.0 - 0.3 * min(abs(d), 3)))

            icon_size = int(44 * scale)
            pix = app_icon(entry.lnk or entry.path, 48)
            cx = self.width() / 2
            if pix is not None:
                p.drawPixmap(QRect(int(cx - icon_size / 2), int(y - icon_size / 2 - 12), icon_size, icon_size), pix)
            else:
                p.setPen(QColor(232, 234, 237))
                p.drawText(
                    QRectF(cx - icon_size / 2, y - icon_size / 2 - 12, icon_size, icon_size),
                    Qt.AlignCenter,
                    (entry.name[:1] or "?").upper(),
                )

            font = p.font()
            font.setPointSize(max(7, int(9 * scale)))
            p.setFont(font)
            p.setPen(QColor(232, 234, 237))
            p.drawText(QRectF(0, y + icon_size / 2 - 8, self.width(), 22), Qt.AlignHCenter, entry.name)
            p.setOpacity(1.0)

        p.setPen(QColor(90, 140, 255))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(self.width() / 2 - 120, center_y - ITEM_H / 2, 240, ITEM_H), 10, 10)