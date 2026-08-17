from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import subprocess
import time
from pathlib import Path
from typing import Optional, Protocol

from . import win32_api as api

GWL_STYLE = -16
WS_CHILD = 0x40000000
WS_POPUP = 0x80000000
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_TOOLWINDOW = 0x00000080
GW_OWNER = 4
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SW_HIDE = 0
SW_SHOW = 5
SW_SHOWNOACTIVATE = 4
WM_SETREDRAW = 0x000B

EVENT_OBJECT_CREATE = 0x8000
EVENT_OBJECT_SHOW = 0x8002
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002

VT_LPWSTR = 31
ERROR_INSUFFICIENT_BUFFER = 122
IID_IPROPERTY_STORE = api.make_guid("{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF90}")
COREWINDOW_CLASS = "Windows.UI.Core.CoreWindow"

_PROTECTED_EXES = {"explorer.exe", "cmd.exe", "conhost.exe", "svchost.exe", "dwm.exe"}

api.user32.GetWindow.restype = api.HWND
api.user32.GetWindow.argtypes = [api.HWND, wintypes.UINT]
api.user32.GetClassNameW.restype = ctypes.c_int
api.user32.GetClassNameW.argtypes = [api.HWND, wintypes.LPWSTR, ctypes.c_int]
api.user32.EnumChildWindows.restype = wintypes.BOOL
api.user32.EnumChildWindows.argtypes = [api.HWND, api.WNDENUMPROC, wintypes.LPARAM]


class ExternalAppError(RuntimeError):
    pass


def parse_aumid(command: str) -> Optional[str]:
    """Extracts the AppUserModelID from a shell:AppsFolder\\<AUMID> command."""
    low = command.lower()
    marker = "shell:appsfolder\\"
    idx = low.find(marker)
    if idx == -1:
        return None
    return command[idx + len(marker):].strip().strip('"') or None


class _PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", api.GUID), ("pid", ctypes.c_ulong)]


class _PROPVARIANT(ctypes.Structure):
    _fields_ = [
        ("vt", ctypes.c_ushort),
        ("r1", ctypes.c_ushort),
        ("r2", ctypes.c_ulong),
        ("pwsz", ctypes.c_void_p),
    ]


class AppEmbedder(Protocol):
    def launch(self, command: str) -> subprocess.Popen: ...
    def begin_tracking(self, sub, pid: int, exe: str, aumid: str) -> None: ...
    def end_tracking(self, sub) -> None: ...
    def find_all_hwnds_for_launch(self, root_pid: int, exe_name: str, aumid: str) -> list[int]: ...
    def find_hwnds_by_aumid(self, aumid: str) -> list[int]: ...
    def snapshot_caption_hwnds(self) -> set[int]: ...
    def is_main_window(self, hwnd: int) -> bool: ...
    def is_descendant_of(self, pid: int, root: int) -> bool: ...
    def is_corewindow_hosted(self, hwnd: int) -> bool: ...
    def resolve_window_aumid(self, hwnd: int, diag: bool = False) -> str: ...
    def process_aumid(self, pid: int, diag: bool = False) -> str: ...
    def window_style(self, hwnd: int) -> int: ...
    def hwnd_text(self, hwnd: int) -> str: ...
    def find_stray_hwnds(self, embedded: list[int], title: str) -> list[int]: ...
    def find_windows_by_title_contains(self, text: str, exclude: list[int]) -> list[int]: ...
    def kill_hwnd_processes(self, hwnds: list[int]) -> int: ...
    def is_visible(self, hwnd: int) -> bool: ...
    def is_hwnd_alive(self, hwnd: int) -> bool: ...
    def hwnd_parent(self, hwnd: int) -> int: ...
    def adopt(self, hwnd: int, parent_hwnd: int, show: bool = True) -> None: ...
    def place(self, hwnd: int, x: int, y: int, width: int, height: int) -> None: ...
    def place_top_level(self, hwnd: int, x: int, y: int, width: int, height: int) -> None: ...
    def show_window(self, hwnd: int, visible: bool) -> None: ...
    def stack_overlay(self, app_hwnd: int, workspace_hwnd: int) -> None: ...
    def set_redraw(self, hwnd: int, on: bool) -> None: ...
    def force_redraw(self, hwnd: int) -> None: ...


class NullAppEmbedder:
    def launch(self, command: str) -> subprocess.Popen:
        raise ExternalAppError("External app embedding requires Windows.")
    def begin_tracking(self, sub, pid, exe, aumid): pass
    def end_tracking(self, sub): pass
    def find_all_hwnds_for_launch(self, root_pid, exe_name, aumid): return []
    def find_hwnds_by_aumid(self, aumid): return []
    def snapshot_caption_hwnds(self): return set()
    def is_main_window(self, hwnd): return False
    def is_descendant_of(self, pid, root): return False
    def is_corewindow_hosted(self, hwnd): return False
    def resolve_window_aumid(self, hwnd, diag=False): return ""
    def process_aumid(self, pid, diag=False): return ""
    def window_style(self, hwnd): return 0
    def hwnd_text(self, hwnd): return ""
    def find_stray_hwnds(self, embedded, title): return []
    def find_windows_by_title_contains(self, text, exclude): return []
    def kill_hwnd_processes(self, hwnds): return 0
    def is_visible(self, hwnd): return False
    def is_hwnd_alive(self, hwnd): return False
    def hwnd_parent(self, hwnd): return 0
    def adopt(self, hwnd, parent_hwnd, show=True): pass
    def place(self, hwnd, x, y, width, height): pass
    def place_top_level(self, hwnd, x, y, width, height): pass
    def show_window(self, hwnd, visible): pass
    def stack_overlay(self, app_hwnd, workspace_hwnd): pass
    def set_redraw(self, hwnd, on): pass
    def force_redraw(self, hwnd): pass


class Win32AppEmbedder:
    """Typed, architecture-safe embedder.

    Two embedding strategies:
    - reparented (SetParent into WS_CHILD): ordinary Win32 HWNDs, including
      self-hosted MSIX apps (Paint, Terminal);
    - positional overlay (never reparented): CoreWindow/XAML UWP apps whose
      composition engine crashes under SetParent (Calculator, Clock).
    """

    def __init__(self) -> None:
        self._tracking: dict[int, tuple] = {}  # id(sub) -> (sub, pid, exe_lower, aumid)
        self._hook = None
        self._hook_proc = api.WINEVENTPROC(self._on_win_event)
        self._install_hook()

    # -- canonical predicate ----------------------------------------------------

    def is_main_window(self, hwnd: int) -> bool:
        """Visible, captioned, not a child, not a tool window, and unowned."""
        if not api.user32.IsWindowVisible(hwnd):
            return False
        style = api.GetWindowLongPtr(hwnd, GWL_STYLE)
        if not (style & WS_CAPTION):
            return False
        if (style & WS_CHILD) or (style & WS_TOOLWINDOW):
            return False
        if api.user32.GetWindow(hwnd, GW_OWNER):
            return False
        return True

    def is_descendant_of(self, pid: int, root: int) -> bool:
        return bool(root) and pid in self._process_tree_pids(root)

    def is_corewindow_hosted(self, hwnd: int) -> bool:
        """Frame-host for a CoreWindow (XAML UWP) app => reparenting crashes it."""
        if self.process_aumid(self._window_pid(hwnd)):
            return False  # own process carries identity: reparent-safe family
        return bool(self._corewindow_child_pid(hwnd))

    # -- creation hook ----------------------------------------------------------

    def _install_hook(self) -> None:
        self._hook = api.user32.SetWinEventHook(
            EVENT_OBJECT_CREATE, EVENT_OBJECT_SHOW, None, self._hook_proc,
            0, 0, WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS,
        )

    def _on_win_event(self, _h, event, hwnd, id_object, id_child, _thread, _time) -> None:
        if event not in (EVENT_OBJECT_CREATE, EVENT_OBJECT_SHOW):
            return
        if id_object != 0 or id_child != 0 or not hwnd:
            return
        if not self._tracking:
            return
        if not self.is_main_window(hwnd):
            return

        pid = self._window_pid(hwnd)
        image_base = ""
        win_aumid = ""
        for sub, track_pid, track_exe, track_aumid in list(self._tracking.values()):
            if sub._embedded_hwnds or hwnd in sub._embedded_hwnds:
                continue
            if pid == track_pid:
                self._safe_ingest(sub, hwnd)
                continue
            if track_exe:
                if not image_base:
                    image = self._process_image(pid)
                    image_base = os.path.basename(image).lower() if image else ""
                if image_base == track_exe:
                    self._safe_ingest(sub, hwnd)
                    continue
            if track_aumid:
                if not win_aumid:
                    win_aumid = self.resolve_window_aumid(hwnd)
                if win_aumid and win_aumid == track_aumid:
                    self._safe_ingest(sub, hwnd)

    @staticmethod
    def _safe_ingest(sub, hwnd: int) -> None:
        try:
            sub.ingest_hwnd(hwnd)
        except Exception:
            pass

    def _window_pid(self, hwnd: int) -> int:
        pid = ctypes.c_ulong()
        api.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    # -- AUMID identification ----------------------------------------------------

    def _corewindow_child_pid(self, hwnd: int) -> int:
        """Pid of the real app process behind a shared ApplicationFrameHost window."""
        found: list[int] = []

        def callback(child, _lparam):
            buf = ctypes.create_unicode_buffer(256)
            api.user32.GetClassNameW(child, buf, 256)
            if buf.value == COREWINDOW_CLASS:
                found.append(self._window_pid(child))
                return False
            return True

        api.user32.EnumChildWindows(hwnd, api.WNDENUMPROC(callback), 0)
        return found[0] if found else 0

    def process_aumid(self, pid: int, diag: bool = False) -> str:
        """The package AUMID of a process (empty for non-packaged processes)."""
        if not pid:
            return ""
        handle = api.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            if diag:
                print(f"[diag] process_aumid pid={pid} OpenProcess -> NULL", flush=True)
            return ""
        try:
            length = ctypes.c_ulong(0)
            rc = api.kernel32.GetApplicationUserModelId(handle, ctypes.byref(length), None)
            if diag:
                print(f"[diag] process_aumid pid={pid} probe rc={rc} len={length.value}", flush=True)
            if rc != ERROR_INSUFFICIENT_BUFFER or length.value == 0:
                return ""
            buf = ctypes.create_unicode_buffer(length.value)
            rc = api.kernel32.GetApplicationUserModelId(handle, ctypes.byref(length), buf)
            if diag:
                print(f"[diag] process_aumid pid={pid} final rc={rc} aumid={buf.value!r}", flush=True)
            return buf.value if rc == 0 else ""
        except Exception as exc:
            if diag:
                print(f"[diag] process_aumid pid={pid} exception={exc!r}", flush=True)
            return ""
        finally:
            api.kernel32.CloseHandle(handle)

    def window_aumid(self, hwnd: int, diag: bool = False) -> str:
        """Window-level property store AUMID (weak signal; last resort)."""
        store = ctypes.c_void_p()
        hr = api.shell32.SHGetPropertyStoreForWindow(
            hwnd, ctypes.byref(IID_IPROPERTY_STORE), ctypes.byref(store)
        )
        if hr != 0 or not store:
            if diag:
                print(f"[diag] window_aumid hwnd={hwnd} SHGetPropertyStoreForWindow "
                      f"hr={hr & 0xFFFFFFFF:#x} store={bool(store)}", flush=True)
            return ""
        try:
            vt = ctypes.cast(store, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
            get_value = ctypes.CFUNCTYPE(
                ctypes.c_long, ctypes.c_void_p,
                ctypes.POINTER(_PROPERTYKEY), ctypes.POINTER(_PROPVARIANT),
            )(vt[5])
            release = ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vt[2])
            key = _PROPERTYKEY()
            key.fmtid = api.make_guid("{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}")
            key.pid = 5
            prop = _PROPVARIANT()
            value = ""
            gv = get_value(store, ctypes.byref(key), ctypes.byref(prop))
            if gv == 0:
                if prop.vt == VT_LPWSTR and prop.pwsz:
                    value = ctypes.wstring_at(prop.pwsz)
                api.ole32.PropVariantClear(ctypes.byref(prop))
            elif diag:
                print(f"[diag] window_aumid hwnd={hwnd} GetValue hr={gv & 0xFFFFFFFF:#x} "
                      f"vt={prop.vt}", flush=True)
            release(store)
            return value
        except Exception as exc:
            if diag:
                print(f"[diag] window_aumid hwnd={hwnd} exception={exc!r}", flush=True)
            return ""

    def resolve_window_aumid(self, hwnd: int, diag: bool = False) -> str:
        """
        App identity for a top-level window: own process AUMID, then the
        CoreWindow child's process AUMID (frame-hosted UWP), then the window
        property store as a last resort.
        """
        pid = self._window_pid(hwnd)
        aumid = self.process_aumid(pid, diag=diag)
        if aumid:
            return aumid
        child_pid = self._corewindow_child_pid(hwnd)
        if child_pid:
            aumid = self.process_aumid(child_pid, diag=diag)
            if diag:
                print(f"[diag] resolve hwnd={hwnd} frame pid={pid} -> "
                      f"corewindow pid={child_pid} aumid={aumid!r}", flush=True)
            if aumid:
                return aumid
        return self.window_aumid(hwnd, diag=diag)

    def find_hwnds_by_aumid(self, aumid: str) -> list[int]:
        found: list[int] = []
        if not aumid:
            return found

        def callback(hwnd, _lparam):
            if not api.user32.IsWindowVisible(hwnd):
                return True
            style = api.GetWindowLongPtr(hwnd, GWL_STYLE)
            if not (style & WS_CAPTION):
                return True
            if self.resolve_window_aumid(hwnd) == aumid:
                found.append(hwnd)
            return True

        api.user32.EnumWindows(api.WNDENUMPROC(callback), 0)
        return found

    def begin_tracking(self, sub, pid: int, exe: str, aumid: str) -> None:
        self._tracking[id(sub)] = (sub, pid, (exe or "").lower(), aumid or "")

    def end_tracking(self, sub) -> None:
        self._tracking.pop(id(sub), None)

    # -- launching -----------------------------------------------------------

    def launch(self, command: str) -> subprocess.Popen:
        if not command.strip():
            raise ExternalAppError("Command is required.")
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        candidate = command.strip().strip('"')
        try:
            if os.path.isfile(candidate):
                return subprocess.Popen([candidate], cwd=str(Path(candidate).parent),
                                        startupinfo=startup, creationflags=flags)
        except (ValueError, OSError):
            pass
        try:
            return subprocess.Popen(command, shell=True, startupinfo=startup, creationflags=flags)
        except OSError as error:
            raise ExternalAppError(f"Could not launch: {command}") from error

    # -- discovery -------------------------------------------------------------

    def find_all_hwnds_for_launch(self, root_pid: int, exe_name: str, aumid: str) -> list[int]:
        tree = self._process_tree_pids(root_pid)
        exe_name = (exe_name or "").lower()
        visible: list[int] = []
        hidden: list[int] = []

        def callback(hwnd, _lparam):
            if not self.is_main_window(hwnd):
                return True
            window_pid = self._window_pid(hwnd)
            match = window_pid in tree
            if not match and exe_name:
                image = self._process_image(window_pid)
                match = bool(image) and os.path.basename(image).lower() == exe_name
            if not match and aumid:
                match = self.resolve_window_aumid(hwnd) == aumid
            if match:
                (visible if api.user32.IsWindowVisible(hwnd) else hidden).append(hwnd)
            return True

        api.user32.EnumWindows(api.WNDENUMPROC(callback), 0)
        return visible + hidden

    def snapshot_caption_hwnds(self) -> set[int]:
        found: set[int] = set()

        def callback(hwnd, _lparam):
            if api.user32.IsWindowVisible(hwnd):
                style = api.GetWindowLongPtr(hwnd, GWL_STYLE)
                if style & WS_CAPTION:
                    found.add(hwnd)
            return True

        api.user32.EnumWindows(api.WNDENUMPROC(callback), 0)
        return found

    def hwnd_text(self, hwnd: int) -> str:
        buf = ctypes.create_unicode_buffer(512)
        api.user32.GetWindowTextW(hwnd, buf, 512)
        return buf.value

    def find_stray_hwnds(self, embedded: list[int], title: str) -> list[int]:
        embedded_set = set(embedded)
        strays: list[int] = []
        if not title:
            return strays

        def callback(hwnd, _lparam):
            if hwnd in embedded_set or not api.user32.IsWindowVisible(hwnd):
                return True
            style = api.GetWindowLongPtr(hwnd, GWL_STYLE)
            if not (style & WS_CAPTION):
                return True
            if self.hwnd_text(hwnd) == title:
                strays.append(hwnd)
            return True

        api.user32.EnumWindows(api.WNDENUMPROC(callback), 0)
        return strays

    def find_windows_by_title_contains(self, text: str, exclude: list[int]) -> list[int]:
        exclude_set = set(exclude)
        needle = text.lower()
        found: list[int] = []
        if not needle:
            return found

        def callback(hwnd, _lparam):
            if hwnd in exclude_set or not api.user32.IsWindowVisible(hwnd):
                return True
            style = api.GetWindowLongPtr(hwnd, GWL_STYLE)
            if not (style & WS_CAPTION):
                return True
            if needle in self.hwnd_text(hwnd).lower():
                found.append(hwnd)
            return True

        api.user32.EnumWindows(api.WNDENUMPROC(callback), 0)
        return found

    def kill_hwnd_processes(self, hwnds: list[int]) -> int:
        killed: set[int] = set()
        for hwnd in hwnds:
            if not api.user32.IsWindow(hwnd):
                continue
            pid = self._window_pid(hwnd)
            if pid in killed or pid <= 4:
                continue
            image = self._process_image(pid)
            if not image or os.path.basename(image).lower() in _PROTECTED_EXES:
                continue
            if "applicationframehost.exe" not in image.lower():
                handle = api.kernel32.OpenProcess(0x0001, False, pid)
                if handle:
                    api.kernel32.TerminateProcess(handle, 0)
                    api.kernel32.CloseHandle(handle)
                    killed.add(pid)
                continue
            # Shared frame host: kill only the tenant app behind the CoreWindow.
            child_pid = self._corewindow_child_pid(hwnd)
            if child_pid and child_pid not in killed:
                handle = api.kernel32.OpenProcess(0x0001, False, child_pid)
                if handle:
                    api.kernel32.TerminateProcess(handle, 0)
                    api.kernel32.CloseHandle(handle)
                    killed.add(child_pid)
        return len(killed)

    # -- embedding: reparented ----------------------------------------------------

    def is_visible(self, hwnd: int) -> bool:
        return bool(api.user32.IsWindowVisible(hwnd))

    def is_hwnd_alive(self, hwnd: int) -> bool:
        return bool(api.user32.IsWindow(hwnd))

    def hwnd_parent(self, hwnd: int) -> int:
        return int(api.user32.GetParent(hwnd) or 0)

    def adopt(self, hwnd: int, parent_hwnd: int, show: bool = True) -> None:
        api.user32.SetParent(hwnd, parent_hwnd)
        style = api.GetWindowLongPtr(hwnd, GWL_STYLE)
        style &= ~(WS_POPUP | WS_CAPTION | WS_THICKFRAME | WS_SYSMENU
                   | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
        style |= WS_CHILD
        api.SetWindowLongPtr(hwnd, GWL_STYLE, style)
        api.user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                                SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)
        if show:
            api.user32.ShowWindow(hwnd, SW_SHOW)

    def place(self, hwnd: int, x: int, y: int, width: int, height: int) -> None:
        api.user32.MoveWindow(hwnd, x, y, width, height, True)

    # -- embedding: positional overlay ---------------------------------------------

    def place_top_level(self, hwnd: int, x: int, y: int, width: int, height: int) -> None:
        """Move/resize a real top-level window without touching its hierarchy."""
        api.user32.SetWindowPos(hwnd, None, x, y, width, height,
                                SWP_NOZORDER | SWP_NOACTIVATE)

    def show_window(self, hwnd: int, visible: bool) -> None:
        api.user32.ShowWindow(hwnd, SW_SHOW if visible else SW_HIDE)

    def stack_overlay(self, app_hwnd: int, workspace_hwnd: int) -> None:
        """Keep the overlay app directly above the workspace in z-order."""
        api.user32.SetWindowPos(workspace_hwnd, app_hwnd, 0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    # -- redraw helpers --------------------------------------------------------------

    def set_redraw(self, hwnd: int, on: bool) -> None:
        api.user32.SendMessageW(hwnd, WM_SETREDRAW, 1 if on else 0, 0)

    def force_redraw(self, hwnd: int) -> None:
        api.user32.RedrawWindow(hwnd, None, None, 0x0001 | 0x0002 | 0x0004 | 0x0100)

    # -- process helpers --------------------------------------------------------------

    def _process_tree_pids(self, root: int) -> set[int]:
        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize", ctypes.c_ulong), ("cntUsage", ctypes.c_ulong),
                ("th32ProcessID", ctypes.c_ulong),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", ctypes.c_ulong), ("cntThreads", ctypes.c_ulong),
                ("th32ParentProcessID", ctypes.c_ulong),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", ctypes.c_ulong),
                ("szExeFile", ctypes.c_char * 260),
            ]

        snap = api.kernel32.CreateToolhelp32Snapshot(0x2, 0)
        if snap in (None, api.INVALID_HANDLE):
            return {root}
        parent_map: dict[int, int] = {}
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        try:
            if api.kernel32.Process32First(snap, ctypes.byref(entry)):
                while True:
                    parent_map[entry.th32ProcessID] = entry.th32ParentProcessID
                    if not api.kernel32.Process32Next(snap, ctypes.byref(entry)):
                        break
        finally:
            api.kernel32.CloseHandle(snap)
        tree = {root}
        changed = True
        while changed:
            changed = False
            for pid, parent in parent_map.items():
                if pid not in tree and parent in tree:
                    tree.add(pid)
                    changed = True
        return tree

    def _process_image(self, pid: int) -> Optional[str]:
        handle = api.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        try:
            buf = ctypes.create_unicode_buffer(260)
            size = ctypes.c_ulong(260)
            if api.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return buf.value
            return None
        finally:
            api.kernel32.CloseHandle(handle)


def create_app_embedder() -> AppEmbedder:
    return Win32AppEmbedder() if os.name == "nt" else NullAppEmbedder()