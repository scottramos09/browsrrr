from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .canvas import DRAW_HOLD_MS
from .domain import Rect
from .monitor_spanner import clamped_rect


class Workspace(QWidget):
    """Infinite canvas bounded by the logical monitor layout."""

    new_web_requested = Signal(QPoint)      # Ctrl+left-click
    app_reel_requested = Signal(QPoint)     # right-click
    workspace_resized = Signal(int, int, int, int)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._path = QPainterPath()
        self._drawing = False
        self._press_pos = QPoint()

        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.setInterval(DRAW_HOLD_MS)
        self._hold_timer.timeout.connect(self._begin_stroke)

    def accommodate_subwindow(self, sub: QWidget) -> None:
        rect = sub.geometry()

        dx_left = min(0, rect.x())
        dy_top = min(0, rect.y())
        dx_right = max(0, rect.right() - self.width())
        dy_bottom = max(0, rect.bottom() - self.height())

        if dx_left == 0 and dy_top == 0 and dx_right == 0 and dy_bottom == 0:
            return

        new_width = self.width() - dx_left + dx_right
        new_height = self.height() - dy_top + dy_bottom

        shift_x = -dx_left
        shift_y = -dy_top

        for child in self.children():
            if child is not sub and isinstance(child, QWidget):
                child.move(child.x() + shift_x, child.y() + shift_y)

        sub.move(rect.x() + shift_x, rect.y() + shift_y)
        self.resize(new_width, new_height)
        self.workspace_resized.emit(dx_left, dy_top, new_width, new_height)

    def clamp_subwindows(self) -> None:
        bounds = Rect(0, 0, self.width(), self.height())
        for child in list(self.children()):
            if not isinstance(child, QWidget):
                continue
            r = child.geometry()
            c = clamped_rect(Rect(r.x(), r.y(), r.width(), r.height()), bounds)
            if (c.x, c.y, c.width, c.height) != (r.x(), r.y(), r.width(), r.height()):
                child.setGeometry(c.x, c.y, c.width, c.height)

    def _begin_stroke(self) -> None:
        self._drawing = True
        self._path.moveTo(self._press_pos)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.RightButton:
            self.app_reel_requested.emit(event.position().toPoint())
            return
        if event.button() != Qt.LeftButton:
            return
        if event.modifiers() & Qt.ControlModifier:
            self.new_web_requested.emit(event.position().toPoint())
            return
        self._press_pos = event.position().toPoint()
        self._hold_timer.start()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drawing:
            self._path.lineTo(event.position().toPoint())
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._hold_timer.stop()
        self._drawing = False

    def contextMenuEvent(self, event) -> None:
        event.accept()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#202124"))
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#E8EAED"), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(self._path)