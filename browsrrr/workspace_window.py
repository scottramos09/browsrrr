from __future__ import annotations

import ctypes
import ctypes.wintypes
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QThread, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .ai_panel import AiPanelWidget
from .ai_service import AiAgent
from .app_catalog import (
    AppEntry,
    block_entry,
    catalog_file,
    load_blocked,
    load_entries,
    record_recent,
    recents_file,
    save_entries,
    scan_all_apps,
)
from .app_reel import AppReel
from .code_editor_widget import CodeEditorWidget
from .code_runner import CodeRunner
from .config import Settings, save_settings
from .monitor_spanner import combined_rect
from .qt_monitors import domain_screens, virtual_bounds
from .session import load_session, save_session
from .settings_dialog import SettingsDialog
from .sub_window import SubWindow, SubWindowResizeFilter
from .title_bar import CONTROLS_WIDTH, TITLE_BAR_HEIGHT, TitleBar, WindowControlsWidget
from .web_subwindow import WebSubWindowContent
from .win32_embedder import AppEmbedder, ExternalAppError, parse_aumid
from .workspace import Workspace

RESIZE_MARGIN = 8
MIN_WINDOW_WIDTH = 400
MIN_WINDOW_HEIGHT = 300

WM_NCHITTEST = 0x0084
WM_SIZING = 0x0214
WM_MOVING = 0x0216
HT_CAPTION = 2
HT_LEFT, HT_RIGHT, HT_TOP = 10, 11, 12
HT_TOPLEFT, HT_TOPRIGHT = 13, 14
HT_BOTTOM, HT_BOTTOMLEFT, HT_BOTTOMRIGHT = 15, 16, 17


def clamp_to_bounds(x: int, y: int, w: int, h: int) -> tuple[int, int, int, int]:
    bounds = virtual_bounds()
    w = min(w, bounds.width)
    h = min(h, bounds.height)
    x = min(max(x, bounds.x), bounds.x + max(0, bounds.width - w))
    y = min(max(y, bounds.y), bounds.y + max(0, bounds.height - h))
    return x, y, w, h


class CatalogWorker(QThread):
    catalog_ready = Signal(list)

    def run(self) -> None:
        self.catalog_ready.emit(scan_all_apps())


class OutsideClickFilter(QObject):
    """Dismisses the app reel on any left-click outside of it."""

    def __init__(self, reel_getter) -> None:
        super().__init__()
        self._reel_getter = reel_getter

    def eventFilter(self, obj, event) -> bool:
        reel = self._reel_getter()
        if reel is None:
            return False
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            if isinstance(obj, QWidget) and obj is not reel and not reel.isAncestorOf(obj):
                reel.dismissed.emit()
                return True  # the click only closes the reel
        return False


class TaskbarWidget(QWidget):
    """Tray holding minimized subwindows."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setStyleSheet("TaskbarWidget { background: #1e1e1e; border-top: 1px solid #444; }")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(8, 4, 8, 4)
        self._layout.setSpacing(8)
        self._layout.addStretch()
        self._buttons: dict[SubWindow, QPushButton] = {}

    def add_subwindow(self, sub: SubWindow, title: str) -> None:
        if sub in self._buttons:
            return
        button = QPushButton(title)
        button.setFixedHeight(28)
        button.setStyleSheet(
            "QPushButton { background: #303134; color: #eee; padding: 0 12px; "
            "border: 1px solid #5F6368; } QPushButton:hover { background: #3C4043; }"
        )
        button.clicked.connect(lambda: sub.toggle_minimize())
        self._layout.insertWidget(self._layout.count() - 1, button)
        self._buttons[sub] = button
        sub.hide()

    def remove_subwindow(self, sub: SubWindow) -> None:
        button = self._buttons.pop(sub, None)
        if button is not None:
            self._layout.removeWidget(button)
            button.deleteLater()


class DownloadManagerWidget(QWidget):
    """Tracks Chromium downloads with per-item progress."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self._list_layout = QVBoxLayout()
        layout.addLayout(self._list_layout)
        layout.addStretch()

    def add_download(self, item) -> None:
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)

        name = item.url().fileName() or item.url().toString().split("/")[-1]
        label = QLabel(name)
        label.setStyleSheet("color: #eee;")
        progress = QProgressBar()
        progress.setFixedWidth(120)
        progress.setFixedHeight(20)

        row.addWidget(label, 1)
        row.addWidget(progress)
        self._list_layout.addWidget(row_widget)

        item.accept()
        item.receivedBytesChanged.connect(lambda: self._update_progress(item, progress))
        item.isFinishedChanged.connect(lambda: self._finish_download(item, label, progress))

    @staticmethod
    def _update_progress(item, progress: QProgressBar) -> None:
        total = item.totalBytes()
        if total > 0:
            progress.setValue(int((item.receivedBytes() / total) * 100))
        else:
            progress.setRange(0, 0)

    @staticmethod
    def _finish_download(item, label: QLabel, progress: QProgressBar) -> None:
        if item.state() == 2:  # DownloadCompleted
            label.setText(f"{label.text()} (Done)")
            progress.hide()


class WorkspaceWindow(QMainWindow):
    def __init__(
        self,
        ai_agent: AiAgent,
        embedder: AppEmbedder,
        code_runner: CodeRunner,
        settings: Settings,
        settings_path: Path,
        session_path: Path,
    ) -> None:
        super().__init__()
        self._ai_agent = ai_agent
        self._embedder = embedder
        self._code_runner = code_runner
        self._settings = settings
        self._settings_path = settings_path
        self._session_path = session_path
        self._web_subs: dict[SubWindow, WebSubWindowContent] = {}
        self._shortcuts: list[QShortcut] = []
        self._spanned = False
        self._pre_span: tuple[int, int, int, int] | None = None
        self._floating_controls: dict[str, WindowControlsWidget] = {}
        self._reel: AppReel | None = None
        self._index: list[AppEntry] = load_entries(catalog_file())
        self._catalog_worker: CatalogWorker | None = None

        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.resize(1280, 800)

        container = QWidget(self)
        self._container = container
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._workspace = Workspace(container)
        self._workspace.new_web_requested.connect(self._spawn_web_at)
        self._workspace.app_reel_requested.connect(self._open_app_reel)
        self._workspace.workspace_resized.connect(self._on_workspace_resized)

        self._taskbar = TaskbarWidget(container)

        self._title_bar = TitleBar(
            container,
            on_minimize=self.showMinimized,
            on_maximize=self.toggle_span,
            on_close=self.close,
            actions=[
                ("Coder", self.open_coder_subwindow),
                ("AI", self.open_ai_subwindow),
                ("Embed", self.request_embed_app),
                ("Downloads", self.open_downloads_subwindow),
                ("Settings", self.open_settings),
            ],
        )

        layout.addWidget(self._title_bar)
        layout.addWidget(self._workspace, 1)
        layout.addWidget(self._taskbar)
        self.setCentralWidget(container)

        self.setMinimumWidth(self._title_bar.sizeHint().width() + 24)
        self.setMinimumHeight(MIN_WINDOW_HEIGHT)

        app = QApplication.instance()
        self._sub_resize_filter = SubWindowResizeFilter()
        app.installEventFilter(self._sub_resize_filter)
        self._outside_filter = OutsideClickFilter(lambda: self._reel)
        app.installEventFilter(self._outside_filter)

        app.screenAdded.connect(lambda *_: self._update_floating_controls())
        app.screenRemoved.connect(lambda *_: self._update_floating_controls())

        # Build the Start-Menu app index in the background.
        self._catalog_worker = CatalogWorker()
        self._catalog_worker.catalog_ready.connect(self._on_catalog_ready)
        self._catalog_worker.start()

        self._bind_shortcuts()
        self._restore_session()
        self._update_floating_controls()

    # -- native smooth resize/move with logical-bound clamping ----------------

    def nativeEvent(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(int(message))

            if msg.message == WM_NCHITTEST:
                hit = self._native_hit_test(msg.lParam)
                if hit is not None:
                    return True, hit

            elif msg.message in (WM_SIZING, WM_MOVING):
                rect = ctypes.wintypes.RECT.from_address(msg.lParam)
                x, y = rect.left, rect.top
                w, h = rect.right - rect.left, rect.bottom - rect.top
                if msg.message == WM_SIZING:
                    w = max(w, self.minimumWidth())
                    h = max(h, self.minimumHeight())
                x, y, w, h = clamp_to_bounds(x, y, w, h)
                rect.left, rect.top = x, y
                rect.right, rect.bottom = x + w, y + h
                return True, 1

        return super().nativeEvent(eventType, message)

    def _native_hit_test(self, lparam: int):
        x = ctypes.c_short(lparam & 0xFFFF).value
        y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
        pos = self.mapFromGlobal(QPoint(x, y))

        child = self.childAt(pos)
        while child is not None:
            if isinstance(child, (QPushButton, SubWindow)):
                return None
            child = child.parentWidget()

        left = pos.x() <= RESIZE_MARGIN
        right = pos.x() >= self.width() - RESIZE_MARGIN
        top = pos.y() <= RESIZE_MARGIN
        bottom = pos.y() >= self.height() - RESIZE_MARGIN

        if top and left: return HT_TOPLEFT
        if top and right: return HT_TOPRIGHT
        if bottom and left: return HT_BOTTOMLEFT
        if bottom and right: return HT_BOTTOMRIGHT
        if left: return HT_LEFT
        if right: return HT_RIGHT
        if top: return HT_TOP
        if bottom: return HT_BOTTOM
        if pos.y() <= TITLE_BAR_HEIGHT:
            return HT_CAPTION
        return None

    # -- logical bounds / differential spanning -------------------------------

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        self._update_floating_controls()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._workspace.clamp_subwindows()
        self._update_floating_controls()

    def _update_floating_controls(self) -> None:
        geo = self.geometry()
        needed: dict[str, tuple[int, int]] = {}

        for screen in domain_screens():
            r = screen.rect
            x1, y1 = max(r.x, geo.x()), max(r.y, geo.y())
            x2, y2 = min(r.right, geo.right()), min(r.bottom, geo.bottom())
            if x2 <= x1 or y2 <= y1:
                continue
            if y1 - geo.y() < TITLE_BAR_HEIGHT:
                continue
            needed[screen.name] = (x2 - geo.x() - CONTROLS_WIDTH - 8, y1 - geo.y() + 8)

        for name in list(self._floating_controls):
            if name not in needed:
                self._floating_controls.pop(name).deleteLater()

        for name, (x, y) in needed.items():
            controls = self._floating_controls.get(name)
            if controls is None:
                controls = WindowControlsWidget(
                    self._container, self.showMinimized, self.toggle_span, self.close
                )
                self._floating_controls[name] = controls
            controls.move(x, y)
            controls.show()
            controls.raise_()

    def _on_workspace_resized(self, dx_left: int, dy_top: int, new_width: int, new_height: int) -> None:
        geo = self.geometry()
        x, y, w, h = clamp_to_bounds(
            geo.left() + dx_left,
            geo.top() + dy_top,
            max(new_width, self.minimumWidth()),
            new_height + TITLE_BAR_HEIGHT + self._taskbar.height(),
        )
        self.setGeometry(x, y, w, h)
        self._workspace.clamp_subwindows()

    # -- app reel: complete index, recents when idle ---------------------------

    def _on_catalog_ready(self, entries: list[AppEntry]) -> None:
        self._index = entries
        save_entries(catalog_file(), entries)
        self.statusBar().showMessage(f"App index ready: {len(entries)} apps", 4000)

    def _open_app_reel(self, pos) -> None:
        if self._reel is not None:
            self._reel.close()
            self._reel = None

        recents = load_entries(recents_file())
        index = list(self._index)

        reel = AppReel(recents, index, self._container)
        rx = min(max(8, pos.x() - reel.width() // 2), self.width() - reel.width() - 8)
        ry = min(max(8, pos.y() - reel.height() // 2), self.height() - reel.height() - 8)
        reel.move(rx, ry)
        reel.app_chosen.connect(self._launch_from_reel)
        reel.dismissed.connect(lambda: self._close_reel())
        self._reel = reel
        reel.show()
        reel.raise_()

    def _close_reel(self) -> None:
        if self._reel is not None:
            self._reel.deleteLater()
            self._reel = None

    def _launch_from_reel(self, entry: AppEntry) -> None:
        self._close_reel()
        self.open_external_subwindow(entry.path)

    # -- launch routing ---------------------------------------------------------

    @staticmethod
    def _is_packaged(command: str) -> bool:
        if parse_aumid(command):
            return True
        cand = command.strip().strip('"')
        return ":\\" in cand and "\\windowsapps\\" in cand.lower()

    def open_external_subwindow(self, command: str) -> None:
        aumid = parse_aumid(command)
        exe_name = "" if aumid else Path(command.strip().strip('"')).name

        # WindowsApps-packaged exes cannot be reparented; run them normally.
        if not aumid and self._is_packaged(command):
            self._launch_external_only(command)
            return

        try:
            snapshot = self._embedder.snapshot_caption_hwnds()
            process = self._embedder.launch(command)
            hwnd = self._embedder.find_main_hwnd_for_command(
                process.pid, command, timeout_seconds=3.0
            )
        except ExternalAppError as error:
            self.statusBar().showMessage(str(error), 6000)
            return
        record_recent(command)
        sub = SubWindow(
            command, self._workspace,
            on_bounds_changed=self._workspace.accommodate_subwindow,
            embedder=self._embedder,
            embedded_hwnd=hwnd,
            embedded_exe=exe_name,
            embedded_pid=process.pid,
            embedded_aumid=aumid,
            embedded_snapshot=snapshot,
            embedded_command=command,
        )
        self._wire_subwindow(sub)
        self._place_subwindow(sub, None, None)

    def _launch_external_only(self, command: str) -> None:
        """WindowsApps-packaged exes cannot be reparented; run them normally."""
        try:
            self._embedder.launch(command)
        except ExternalAppError as error:
            self.statusBar().showMessage(str(error), 6000)
            return
        record_recent(command)
        self.statusBar().showMessage(
            f"{self._expected_name(command)} runs as a normal window (Windows blocks UWP embedding)",
            6000,
        )

    # -- subwindow factories ------------------------------------------------

    def open_web_subwindow(self, url: str = "https://www.google.com", rect=None, at=None) -> None:
        content = WebSubWindowContent()
        content.load(url)
        sub = SubWindow("Web", self._workspace, on_bounds_changed=self._workspace.accommodate_subwindow)
        sub.set_content(content)
        self._wire_subwindow(sub)
        self._place_subwindow(sub, rect, at)
        self._web_subs[sub] = content
        sub.destroyed.connect(lambda *_: self._web_subs.pop(sub, None))

    def open_coder_subwindow(self) -> None:
        sub = SubWindow("Coder", self._workspace, on_bounds_changed=self._workspace.accommodate_subwindow)
        sub.set_content(CodeEditorWidget(self._code_runner))
        self._wire_subwindow(sub)
        self._place_subwindow(sub, None, None)

    def open_ai_subwindow(self) -> None:
        sub = SubWindow("AI", self._workspace, on_bounds_changed=self._workspace.accommodate_subwindow)
        sub.set_content(AiPanelWidget(self._ai_agent))
        self._wire_subwindow(sub)
        self._place_subwindow(sub, None, None)

    def open_downloads_subwindow(self) -> None:
        downloader = DownloadManagerWidget()
        sub = SubWindow("Downloads", self._workspace, on_bounds_changed=self._workspace.accommodate_subwindow)
        sub.set_content(downloader)
        self._wire_subwindow(sub)
        self._place_subwindow(sub, None, None)
        QWebEngineProfile.defaultProfile().downloadRequested.connect(downloader.add_download)

    def request_embed_app(self) -> None:
        command, ok = QInputDialog.getText(
            self, "Embed Application", "Command:", text=self._settings.last_embed_command
        )
        if not (ok and command.strip()):
            return
        self._settings.last_embed_command = command.strip()
        save_settings(self._settings, self._settings_path)
        self.open_external_subwindow(command.strip())

    def open_settings(self) -> None:
        dialog = SettingsDialog(self._settings, self)
        if dialog.exec():
            self._settings = dialog.get_settings()
            save_settings(self._settings, self._settings_path)

    # -- subwindow plumbing ---------------------------------------------------

    def _wire_subwindow(self, sub: SubWindow) -> None:
        sub.minimize_requested.connect(lambda s: self._taskbar.add_subwindow(s, s.windowTitle()))
        sub.restore_requested.connect(self._restore_subwindow)
        sub.embed_failed.connect(self._on_embed_failed)
        sub.destroyed.connect(lambda *_: self._taskbar.remove_subwindow(sub))

    def _on_embed_failed(self, sub: SubWindow, command: str, title: str) -> None:
        """Embed failed: kill strays (AUMID-aware for packaged), block, close."""
        if command:
            block_entry(command)

        targets = list(sub._embedded_hwnds)
        if sub._embedded_aumid:
            targets += self._embedder.find_hwnds_by_aumid(sub._embedded_aumid)
        elif title:
            targets += self._embedder.find_stray_hwnds(sub._embedded_hwnds, title)
        else:
            targets += self._embedder.find_windows_by_title_contains(
                self._expected_name(command), sub._embedded_hwnds
            )
        self._embedder.kill_hwnd_processes(targets)

        name = self._expected_name(command)
        self.statusBar().showMessage(f"{name} cannot be embedded; blocked from reel", 6000)
        sub.close()

    @staticmethod
    def _expected_name(command: str) -> str:
        cmd = command.strip()
        aumid = parse_aumid(cmd)
        if aumid:
            return aumid.split("!")[0].split(".")[-1].split("_")[0] or aumid
        return Path(cmd.strip('"')).stem

    def _restore_subwindow(self, sub: SubWindow) -> None:
        sub.show()
        sub.resize(sub.width(), sub._prev_height)
        self._taskbar.remove_subwindow(sub)
        self._workspace.accommodate_subwindow(sub)

    def _place_subwindow(self, sub: SubWindow, rect, at) -> None:
        if rect:
            sub.setGeometry(*rect)
        else:
            count = len(self._workspace.findChildren(SubWindow))
            sub.move(80 + 32 * count, 60 + 32 * count)
            sub.resize(900, 600)
        sub.show()
        sub.raise_()
        self._workspace.accommodate_subwindow(sub)

    def _spawn_web_at(self, pos) -> None:
        self.open_web_subwindow(at=pos)

    # -- window-level actions ---------------------------------------------------

    def toggle_span(self) -> None:
        if self._spanned and self._pre_span is not None:
            self.setGeometry(*self._pre_span)
            self._spanned = False
            return
        geometry = self.geometry()
        self._pre_span = (geometry.x(), geometry.y(), geometry.width(), geometry.height())
        virtual = combined_rect(domain_screens())
        self.setGeometry(virtual.x, virtual.y, virtual.width, virtual.height)
        self._spanned = True

    # -- session ------------------------------------------------------------------

    def _restore_session(self) -> None:
        session = load_session(self._session_path)
        if "geometry" in session:
            x, y, w, h = session["geometry"]
            w = max(w, self.minimumWidth())
            h = max(h, self.minimumHeight())
            self.setGeometry(*clamp_to_bounds(x, y, w, h))

        subs = session.get("web_subs")
        if subs is None:
            self.open_web_subwindow()
            return
        for entry in subs:
            self.open_web_subwindow(url=entry.get("url", "https://www.google.com"), rect=entry.get("rect"))

    def _save_session(self) -> None:
        geometry = self.geometry()
        save_session(self._session_path, {
            "geometry": [geometry.x(), geometry.y(), geometry.width(), geometry.height()],
            "web_subs": [
                {"url": content.url, "rect": [s.x(), s.y(), s.width(), s.height()]}
                for s, content in self._web_subs.items()
            ],
        })

    # -- shortcuts / lifecycle -------------------------------------------------------

    def _bind_shortcuts(self) -> None:
        self._bind_shortcut("Ctrl+T", lambda: self.open_web_subwindow())
        self._bind_shortcut("Ctrl+Shift+K", self.open_coder_subwindow)
        self._bind_shortcut("Ctrl+Shift+A", self.open_ai_subwindow)
        self._bind_shortcut("Ctrl+Shift+E", self.request_embed_app)
        self._bind_shortcut("Ctrl+Shift+M", self.toggle_span)
        self._bind_shortcut("Ctrl+J", self.open_downloads_subwindow)

    def _bind_shortcut(self, sequence: str, slot) -> None:
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.activated.connect(slot)
        self._shortcuts.append(shortcut)

    def closeEvent(self, event) -> None:
        self._save_session()
        for sub in self._workspace.findChildren(SubWindow):
            sub.close()
        super().closeEvent(event)