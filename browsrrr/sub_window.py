from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QMouseEvent
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from .win32_embedder import AppEmbedder

TITLE_HEIGHT = 36
SUBWINDOW_MARGIN = 6
MIN_SUB_WIDTH = 200
MIN_SUB_HEIGHT = 100
ADOPT_TICKS = 25
ADOPT_INTERVAL_MS = 400
VERIFY_DELAY_WIN32_MS = 2500
VERIFY_DELAY_PACKAGED_MS = 3000
VERIFY_MAX_ATTEMPTS = 3
WS_THICKFRAME = 0x00040000
WS_TOOLWINDOW = 0x00000080


def edges_at(pos: QPoint, rect, margin: int) -> Qt.Edges:
    edges = Qt.Edges()
    if pos.x() <= margin: edges |= Qt.LeftEdge
    if pos.x() >= rect.width() - margin: edges |= Qt.RightEdge
    if pos.y() <= margin: edges |= Qt.TopEdge
    if pos.y() >= rect.height() - margin: edges |= Qt.BottomEdge
    return edges


def cursor_shape_for(edges: Qt.Edges):
    if edges in (Qt.LeftEdge | Qt.TopEdge, Qt.RightEdge | Qt.BottomEdge):
        return Qt.CursorShape.SizeFDiagCursor
    if edges in (Qt.RightEdge | Qt.TopEdge, Qt.LeftEdge | Qt.BottomEdge):
        return Qt.CursorShape.SizeBDiagCursor
    if edges in (Qt.LeftEdge, Qt.RightEdge):
        return Qt.CursorShape.SizeHorCursor
    if edges in (Qt.TopEdge, Qt.BottomEdge):
        return Qt.CursorShape.SizeVerCursor
    return None


class CursorManager:
    def __init__(self) -> None:
        self._active_shape = None

    def show(self, edges: Qt.Edges) -> None:
        shape = cursor_shape_for(edges)
        if shape == self._active_shape:
            return
        if self._active_shape is not None:
            QApplication.restoreOverrideCursor()
            self._active_shape = None
        if shape is not None:
            QApplication.setOverrideCursor(QCursor(shape))
            self._active_shape = shape

    def restore(self) -> None:
        if self._active_shape is not None:
            QApplication.restoreOverrideCursor()
            self._active_shape = None


def find_subwindow(obj: QWidget):
    widget = obj
    while widget is not None:
        if isinstance(widget, SubWindow):
            return widget
        widget = widget.parentWidget()
    return None


class SubWindowResizeFilter(QObject):
    def __init__(self) -> None:
        super().__init__()
        self._sub: Optional[SubWindow] = None
        self._edges = Qt.Edges()
        self._drag_pos = QPoint()
        self._cursor = CursorManager()

    def eventFilter(self, obj, event) -> bool:
        if not isinstance(obj, QWidget) or isinstance(obj, QPushButton):
            return False
        if event.type() == QEvent.MouseButtonPress:
            if event.button() != Qt.LeftButton:
                return False
            sub = find_subwindow(obj)
            if sub is None:
                return False
            pos = sub.mapFromGlobal(obj.mapToGlobal(event.position().toPoint()))
            edges = edges_at(pos, sub.rect(), SUBWINDOW_MARGIN)
            if not edges:
                return False
            self._sub = sub
            self._edges = edges
            self._drag_pos = event.globalPosition().toPoint()
            self._cursor.restore()
            return True
        if event.type() == QEvent.MouseMove:
            if self._sub is not None:
                self._drag(self._sub, event.globalPosition().toPoint())
                return True
            edges = Qt.Edges()
            sub = find_subwindow(obj)
            if sub is not None:
                pos = sub.mapFromGlobal(obj.mapToGlobal(event.position().toPoint()))
                edges = edges_at(pos, sub.rect(), SUBWINDOW_MARGIN)
            self._cursor.show(edges)
            return False
        if event.type() == QEvent.MouseButtonRelease:
            if self._sub is not None:
                self._sub = None
                self._cursor.restore()
                return True
        return False

    def _drag(self, sub: SubWindow, pos: QPoint) -> None:
        geo = sub.geometry()
        dx = pos.x() - self._drag_pos.x()
        dy = pos.y() - self._drag_pos.y()
        if self._edges & Qt.LeftEdge:
            new_left = geo.left() + dx
            if geo.right() - new_left < MIN_SUB_WIDTH: new_left = geo.right() - MIN_SUB_WIDTH
            geo.setLeft(new_left)
        if self._edges & Qt.RightEdge: geo.setRight(geo.right() + dx)
        if self._edges & Qt.TopEdge:
            new_top = geo.top() + dy
            if geo.bottom() - new_top < MIN_SUB_HEIGHT: new_top = geo.bottom() - MIN_SUB_HEIGHT
            geo.setTop(new_top)
        if self._edges & Qt.BottomEdge: geo.setBottom(geo.bottom() + dy)
        if geo.width() >= MIN_SUB_WIDTH and geo.height() >= MIN_SUB_HEIGHT:
            sub.setGeometry(geo)
        self._drag_pos = pos


class SubWindow(QWidget):
    minimize_requested = Signal(object)
    restore_requested = Signal(object)
    embed_failed = Signal(object, str, str)  # (subwindow, command, title)

    def __init__(
        self,
        title: str,
        parent: QWidget,
        on_bounds_changed: Optional[Callable[[QWidget], None]] = None,
        embedder: Optional[AppEmbedder] = None,
        embedded_hwnd: Optional[int] = None,
        embedded_exe: Optional[str] = None,
        embedded_pid: Optional[int] = None,
        embedded_aumid: Optional[str] = None,
        embedded_snapshot: Optional[set[int]] = None,
        embedded_command: str = "",
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self._on_bounds_changed = on_bounds_changed
        self._embedder = embedder
        self._embedded_exe = embedded_exe
        self._embedded_pid = embedded_pid
        self._embedded_aumid = embedded_aumid
        self._embedded_snapshot = embedded_snapshot
        self._embedded_command = embedded_command
        self._embedded_hwnds: list[int] = []
        self._drag_offset = None
        self._adopt_ticks = 0
        self._verified = False
        self._verify_attempts = 0
        self._diag_seen: set[int] = set()

        self._is_maximized = False
        self._is_minimized = False
        self._prev_geometry = None
        self._prev_height = 600

        self.setStyleSheet(
            "SubWindow { background: #2b2b2b; border: 2px solid #555; } "
            "QLabel { color: #eee; } QPushButton { color: #eee; background: transparent; border: none; } "
            "QPushButton:hover { background: #444; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._title_bar = QWidget(self)
        self._title_bar.setFixedHeight(TITLE_HEIGHT)
        self._title_bar.setStyleSheet("background: #202124; border-bottom: 1px solid #444;")

        self._bar_layout = QHBoxLayout(self._title_bar)
        self._bar_layout.setContentsMargins(12, 0, 0, 0)
        self._bar_layout.setSpacing(8)
        self._bar_layout.addWidget(QLabel(title, self._title_bar))
        self._bar_layout.addStretch(1)

        self._min_btn = QPushButton("—"); self._min_btn.setFixedSize(36, TITLE_HEIGHT)
        self._min_btn.clicked.connect(self.toggle_minimize)
        self._max_btn = QPushButton("□"); self._max_btn.setFixedSize(36, TITLE_HEIGHT)
        self._max_btn.clicked.connect(self.toggle_maximize)
        self._close_btn = QPushButton("×"); self._close_btn.setFixedSize(36, TITLE_HEIGHT)
        self._close_btn.setStyleSheet("QPushButton:hover { background: #e81123; }")
        self._close_btn.clicked.connect(self.close)

        self._bar_layout.addWidget(self._min_btn)
        self._bar_layout.addWidget(self._max_btn)
        self._bar_layout.addWidget(self._close_btn)

        self._content_host = QWidget(self)

        root.addWidget(self._title_bar)
        root.addWidget(self._content_host, 1)

        if self._embedder is not None and embedded_hwnd is not None:
            self._content_host.winId()
            self._embedder.adopt(embedded_hwnd, int(self._content_host.winId()), show=True)
            self._embedded_hwnds.append(embedded_hwnd)
            self._place_embedded()

        if self._embedder is not None and (self._embedded_exe or self._embedded_pid or self._embedded_aumid):
            self._embedder.begin_tracking(
                self, self._embedded_pid or 0, self._embedded_exe or "", self._embedded_aumid or ""
            )

        self._adopt_timer = QTimer(self)
        self._adopt_timer.setInterval(ADOPT_INTERVAL_MS)
        self._adopt_timer.timeout.connect(self._adopt_more)

        self._verify_timer = QTimer(self)
        self._verify_timer.setSingleShot(True)
        self._verify_timer.setInterval(
            VERIFY_DELAY_PACKAGED_MS if self._embedded_aumid else VERIFY_DELAY_WIN32_MS
        )
        self._verify_timer.timeout.connect(self._verify_embed)

        if self._embedder is not None and (self._embedded_exe or self._embedded_pid or self._embedded_aumid):
            self._adopt_timer.start()
            self._verify_timer.start()

    # -- embed verification --------------------------------------------------

    def _verify_embed(self) -> None:
        if self._verified or self._embedder is None:
            return

        if not self._embedded_hwnds:
            self._try_reactive_adopt()

        if not self._embedded_hwnds:
            self._verify_attempts += 1
            if self._verify_attempts < VERIFY_MAX_ATTEMPTS:
                self._verify_timer.start()  # grace: retry
                return
            self._verified = True
            self._adopt_timer.stop()
            self.embed_failed.emit(self, self._embedded_command, "")
            return

        self._verified = True
        self._adopt_timer.stop()

        host = int(self._content_host.winId())
        for hwnd in list(self._embedded_hwnds):
            if not self._embedder.is_hwnd_alive(hwnd) or self._embedder.hwnd_parent(hwnd) != host:
                self.embed_failed.emit(self, self._embedded_command, "")
                return

        title = self._embedder.hwnd_text(self._embedded_hwnds[0])
        if title and self._embedder.find_stray_hwnds(self._embedded_hwnds, title):
            self.embed_failed.emit(self, self._embedded_command, title)

    # -- embedded app management -------------------------------------------

    def ingest_hwnd(self, hwnd: int, show: bool = True) -> None:
        """Single adoption path used by the win-event hook and pollers."""
        if self._embedder is None or hwnd in self._embedded_hwnds:
            return
        if not self._embedder.is_hwnd_alive(hwnd):
            return
        print(f"[diag] ingest hwnd={hwnd} title={self._embedder.hwnd_text(hwnd)!r}", flush=True)
        self._embedder.adopt(hwnd, int(self._content_host.winId()), show=show)
        self._embedded_hwnds.append(hwnd)
        self._place_embedded()

    def _adopt_more(self) -> None:
        if self._embedder is None:
            self._adopt_timer.stop()
            return

        if self._embedded_aumid:
            # Packaged apps: match by window/process AUMID, not exe name.
            for hwnd in self._embedder.snapshot_caption_hwnds():
                if hwnd in self._embedded_hwnds:
                    continue
                if self._embedded_snapshot is not None and hwnd in self._embedded_snapshot:
                    continue
                w_aumid = self._embedder.window_aumid(hwnd, diag=True)
                p_aumid = self._embedder.process_aumid(self._embedder._window_pid(hwnd), diag=True)
                if hwnd not in self._diag_seen:
                    self._diag_seen.add(hwnd)
                    print(
                        f"[diag] adopt candidate hwnd={hwnd} "
                        f"title={self._embedder.hwnd_text(hwnd)!r} "
                        f"window_aumid={w_aumid!r} process_aumid={p_aumid!r} "
                        f"want={self._embedded_aumid!r}",
                        flush=True,
                    )
                if w_aumid == self._embedded_aumid or p_aumid == self._embedded_aumid:
                    self.ingest_hwnd(hwnd)
        else:
            for hwnd in self._embedder.find_all_hwnds_for_launch(
                self._embedded_pid or 0, self._embedded_exe or "", ""
            ):
                self.ingest_hwnd(hwnd)
            # Stub/redirector launches: if the classic match found nothing,
            # detect packaged windows created after launch and reclassify.
            if not self._embedded_hwnds:
                self._try_reactive_adopt()

        self._adopt_ticks += 1
        if self._adopt_ticks >= ADOPT_TICKS:
            self._adopt_timer.stop()

    def _try_reactive_adopt(self) -> None:
        if self._embedder is None or self._embedded_snapshot is None:
            return
        for hwnd in self._embedder.snapshot_caption_hwnds():
            if hwnd in self._embedded_snapshot or hwnd in self._embedded_hwnds:
                continue
            style = self._embedder.window_style(hwnd)
            if not (style & WS_THICKFRAME) or (style & WS_TOOLWINDOW):
                continue  # skip toasts/tool windows
            pid = self._embedder._window_pid(hwnd)
            aumid = self._embedder.process_aumid(pid, diag=True) or self._embedder.window_aumid(hwnd, diag=True)
            if not aumid:
                continue
            print(f"[diag] reactive reclassify hwnd={hwnd} aumid={aumid!r}", flush=True)
            self._embedded_aumid = aumid
            self._embedder.begin_tracking(
                self, self._embedded_pid or 0, self._embedded_exe or "", aumid
            )
            self.ingest_hwnd(hwnd)
            return

    def _place_embedded(self) -> None:
        if not self._embedded_hwnds or self._embedder is None:
            return
        m = SUBWINDOW_MARGIN
        w = max(1, self._content_host.width() - 2 * m)
        h = max(1, self._content_host.height() - 2 * m)
        for hwnd in self._embedded_hwnds:
            self._embedder.place(hwnd, m, m, w, h)

    def _set_embedded_redraw(self, on: bool) -> None:
        if self._embedder is None:
            return
        for hwnd in self._embedded_hwnds:
            self._embedder.set_redraw(hwnd, on)
            if on:
                self._embedder.force_redraw(hwnd)

    def set_content(self, widget: QWidget) -> None:
        layout = QVBoxLayout(self._content_host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(widget)

    def toggle_minimize(self) -> None:
        if self._is_minimized:
            self.restore_requested.emit(self)
            self._is_minimized = False
        else:
            self.minimize_requested.emit(self)
            self._is_minimized = True
        self._notify_bounds()

    def toggle_maximize(self) -> None:
        if self._is_maximized:
            self.setGeometry(self._prev_geometry)
            self._is_maximized = False
        else:
            self._prev_geometry = self.geometry()
            self.setGeometry(0, 0, self.parent().width(), self.parent().height())
            self._is_maximized = True
        self._notify_bounds()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        self._notify_bounds()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place_embedded()
        self._notify_bounds()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and event.position().y() <= TITLE_HEIGHT:
            self._drag_offset = event.position().toPoint()
            self._set_embedded_redraw(False)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None:
            self.move(self.mapToParent(event.position().toPoint() - self._drag_offset))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None:
            self._set_embedded_redraw(True)
        self._drag_offset = None

    def _notify_bounds(self) -> None:
        if self._on_bounds_changed is not None:
            self._on_bounds_changed(self)

    def closeEvent(self, event) -> None:
        """Closing a subwindow terminates its embedded app — it never escapes to desktop."""
        self._adopt_timer.stop()
        self._verify_timer.stop()
        if self._embedder is not None:
            self._embedder.end_tracking(self)
            if self._embedded_hwnds:
                self._embedder.kill_hwnd_processes(self._embedded_hwnds)
        super().closeEvent(event)