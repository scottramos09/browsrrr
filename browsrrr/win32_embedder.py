from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Optional, Protocol


class ExternalAppError(RuntimeError):
    pass


class AppEmbedder(Protocol):
    def launch(self, command: str) -> subprocess.Popen: ...
    def find_main_hwnd_for_command(self, pid: int, command: str, timeout_seconds: float = 10.0) -> Optional[int]: ...
    def find_all_hwnds_for_launch(self, root_pid: int, exe_name: str) -> list[int]: ...
    def snapshot_caption_hwnds(self) -> set[int]: ...
    def hwnd_image_name(self, hwnd: int) -> Optional[str]: ...
    def hwnd_text(self, hwnd: int) -> str: ...
    def find_stray_hwnds(self, embedded: list[int], title: str) -> list[int]: ...
    def find_windows_by_title_contains(self, text: str, exclude: list[int]) -> list[int]: ...
    def kill_hwnd_processes(self, hwnds: list[int]) -> int: ...
    def is_visible(self, hwnd: int) -> bool: ...
    def is_hwnd_alive(self, hwnd: int) -> bool: ...
    def hwnd_parent(self, hwnd: int) -> int: ...
    def is_rendering(self, hwnd: int) -> bool: ...
    def adopt(self, hwnd: int, parent_hwnd: int, show: bool = True) -> None: ...
    def place(self, hwnd: int, x: int, y: int, width: int, height: int) -> None: ...
    def set_redraw(self, hwnd: int, on: bool) -> None: ...
    def force_redraw(self, hwnd: int) -> None: ...


_PROTECTED_EXES = {"explorer.exe", "cmd.exe", "conhost.exe", "svchost.exe", "dwm.exe"}


class NullAppEmbedder:
    def launch(self, command: str) -> subprocess.Popen:
        raise ExternalAppError("External app embedding requires Windows.")
    def find_main_hwnd_for_command(self, pid, command, timeout_seconds=10.0): return None
    def find_all_hwnds_for_launch(self, root_pid, exe_name): return []
    def snapshot_caption_hwnds(self): return set()
    def hwnd_image_name(self, hwnd): return None
    def hwnd_text(self, hwnd): return ""
    def find_stray_hwnds(self, embedded, title): return []
    def find_windows_by_title_contains(self, text, exclude): return []
    def kill_hwnd_processes(self, hwnds): return 0
    def is_visible(self, hwnd): return False
    def is_hwnd_alive(self, hwnd): return False
    def hwnd_parent(self, hwnd): return 0
    def is_rendering(self, hwnd): return False
    def adopt(self, hwnd, parent_hwnd, show=True): pass
    def place(self, hwnd, x, y, width, height): pass
    def set_redraw(self, hwnd, on): pass
    def force_redraw(self, hwnd): pass


class Win32AppEmbedder:
    _GWL_STYLE = -16
    _WS_CHILD = 0x40000000
    _WS_POPUP = 0x80000000
    _WS_CAPTION = 0x00C00000
    _WS_THICKFRAME = 0x00040000
    _WS_SYSMENU = 0x00080000
    _WS_MINIMIZEBOX = 0x00020000
    _WS_MAXIMIZEBOX = 0x00010000
    _SWP_NOZORDER = 0x0004
    _SWP_NOACTIVATE = 0x0010
    _SWP_FRAMECHANGED = 0x0020
    _SW_SHOW = 5
    _WM_SETREDRAW = 0x000B

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

    def find_main_hwnd_for_command(self, pid: int, command: str, timeout_seconds: float = 10.0) -> Optional[int]:
        exe_name = os.path.basename(command.strip().strip('"')).lower()
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            found = self.find_all_hwnds_for_launch(pid, exe_name)
            if found:
                return found[0]
            time.sleep(0.2)
        return None

    def find_all_hwnds_for_launch(self, root_pid: int, exe_name: str) -> list[int]:
        import ctypes
        user32 = ctypes.windll.user32
        proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        tree = self._process_tree_pids(root_pid)
        exe_name = (exe_name or "").lower()
        visible: list[int] = []
        hidden: list[int] = []

        def callback(hwnd, _lparam):
            style = user32.GetWindowLongW(hwnd, self._GWL_STYLE) & 0xFFFFFFFF
            if not (style & self._WS_CAPTION):
                return True
            window_pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
            match = window_pid.value in tree
            if not match and exe_name:
                image = self._process_image(window_pid.value)
                match = bool(image) and os.path.basename(image).lower() == exe_name
            if match:
                (visible if user32.IsWindowVisible(hwnd) else hidden).append(hwnd)
            return True

        user32.EnumWindows(proc_type(callback), 0)
        return visible + hidden

    def snapshot_caption_hwnds(self) -> set[int]:
        import ctypes
        user32 = ctypes.windll.user32
        proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        found: set[int] = set()

        def callback(hwnd, _lparam):
            if user32.IsWindowVisible(hwnd):
                style = user32.GetWindowLongW(hwnd, self._GWL_STYLE) & 0xFFFFFFFF
                if style & self._WS_CAPTION:
                    found.add(hwnd)
            return True

        user32.EnumWindows(proc_type(callback), 0)
        return found

    def hwnd_image_name(self, hwnd: int) -> Optional[str]:
        import ctypes
        window_pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        image = self._process_image(window_pid.value)
        return os.path.basename(image) if image else None

    def hwnd_text(self, hwnd: int) -> str:
        import ctypes
        buf = ctypes.create_unicode_buffer(512)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
        return buf.value

    def find_stray_hwnds(self, embedded: list[int], title: str) -> list[int]:
        """Visible caption windows with the same title that are NOT embedded."""
        import ctypes
        user32 = ctypes.windll.user32
        proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        embedded_set = set(embedded)
        strays: list[int] = []
        if not title:
            return strays

        def callback(hwnd, _lparam):
            if hwnd in embedded_set or not user32.IsWindowVisible(hwnd):
                return True
            style = user32.GetWindowLongW(hwnd, self._GWL_STYLE) & 0xFFFFFFFF
            if not (style & self._WS_CAPTION):
                return True
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buf, 512)
            if buf.value == title:
                strays.append(hwnd)
            return True

        user32.EnumWindows(proc_type(callback), 0)
        return strays

    def find_windows_by_title_contains(self, text: str, exclude: list[int]) -> list[int]:
        import ctypes
        user32 = ctypes.windll.user32
        proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        exclude_set = set(exclude)
        needle = text.lower()
        found: list[int] = []
        if not needle:
            return found

        def callback(hwnd, _lparam):
            if hwnd in exclude_set or not user32.IsWindowVisible(hwnd):
                return True
            style = user32.GetWindowLongW(hwnd, self._GWL_STYLE) & 0xFFFFFFFF
            if not (style & self._WS_CAPTION):
                return True
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buf, 512)
            if needle in buf.value.lower():
                found.append(hwnd)
            return True

        user32.EnumWindows(proc_type(callback), 0)
        return found

    def kill_hwnd_processes(self, hwnds: list[int]) -> int:
        import ctypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        killed: set[int] = set()
        for hwnd in hwnds:
            if not user32.IsWindow(hwnd):
                continue
            window_pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
            pid = window_pid.value
            if pid in killed or pid <= 4:
                continue
            image = self._process_image(pid)
            if not image or os.path.basename(image).lower() in _PROTECTED_EXES:
                continue
            handle = kernel32.OpenProcess(0x0001, False, pid)  # PROCESS_TERMINATE
            if handle:
                kernel32.TerminateProcess(handle, 0)
                kernel32.CloseHandle(handle)
                killed.add(pid)
        return len(killed)

    # -- render verification ------------------------------------------------------

    def is_rendering(self, hwnd: int, sample: int = 32) -> bool:
        """Pixel-variance probe: a blank/black client area means the embed isn't rendering."""
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        rect = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        w, h = rect.right - rect.left, rect.bottom - rect.top
        if w < 16 or h < 16:
            return False

        hdc_win = user32.GetDC(hwnd)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_win)
        hbmp = gdi32.CreateCompatibleBitmap(hdc_win, w, h)
        old = gdi32.SelectObject(hdc_mem, hbmp)
        if not user32.PrintWindow(hwnd, hdc_mem, 1):  # PW_CLIENTONLY
            gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_win, 0, 0, 0x00CC0020)  # SRCCOPY

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", ctypes.c_ulong), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                ("biPlanes", ctypes.c_ushort), ("biBitCount", ctypes.c_ushort), ("biCompression", ctypes.c_ulong),
                ("biSizeImage", ctypes.c_ulong), ("biXPelsPerMeter", ctypes.c_long), ("biYPelsPerMeter", ctypes.c_long),
                ("biClrUsed", ctypes.c_ulong), ("biClrImportant", ctypes.c_ulong),
            ]

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        buf = (ctypes.c_ubyte * (w * h * 4))()
        gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf, ctypes.byref(bmi), 0)
        gdi32.SelectObject(hdc_mem, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hwnd, hdc_win)

        colors: set[tuple[int, int, int]] = set()
        stride = w * 4
        step_y = max(1, h // sample)
        step_x = max(1, w // sample)
        for y in range(0, h, step_y):
            for x in range(0, w, step_x):
                i = y * stride + x * 4
                colors.add((buf[i], buf[i + 1], buf[i + 2]))
                if len(colors) >= 4:
                    return True
        return len(colors) >= 2

    # -- embedding -----------------------------------------------------------------

    def is_visible(self, hwnd: int) -> bool:
        import ctypes
        return bool(ctypes.windll.user32.IsWindowVisible(hwnd))

    def is_hwnd_alive(self, hwnd: int) -> bool:
        import ctypes
        return bool(ctypes.windll.user32.IsWindow(hwnd))

    def hwnd_parent(self, hwnd: int) -> int:
        import ctypes
        return int(ctypes.windll.user32.GetParent(hwnd) or 0)

    def adopt(self, hwnd: int, parent_hwnd: int, show: bool = True) -> None:
        import ctypes
        user32 = ctypes.windll.user32
        user32.SetParent(hwnd, parent_hwnd)
        style = user32.GetWindowLongW(hwnd, self._GWL_STYLE) & 0xFFFFFFFF
        style &= ~(self._WS_POPUP | self._WS_CAPTION | self._WS_THICKFRAME
                   | self._WS_SYSMENU | self._WS_MINIMIZEBOX | self._WS_MAXIMIZEBOX) & 0xFFFFFFFF
        style |= self._WS_CHILD
        user32.SetWindowLongW(hwnd, self._GWL_STYLE, style)
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                            self._SWP_NOZORDER | self._SWP_NOACTIVATE | self._SWP_FRAMECHANGED)
        if show:
            user32.ShowWindow(hwnd, self._SW_SHOW)

    def place(self, hwnd: int, x: int, y: int, width: int, height: int) -> None:
        import ctypes
        ctypes.windll.user32.MoveWindow(hwnd, x, y, width, height, True)

    def set_redraw(self, hwnd: int, on: bool) -> None:
        import ctypes
        ctypes.windll.user32.SendMessageW(hwnd, self._WM_SETREDRAW, 1 if on else 0, 0)

    def force_redraw(self, hwnd: int) -> None:
        import ctypes
        ctypes.windll.user32.RedrawWindow(hwnd, None, None, 0x0001 | 0x0002 | 0x0004 | 0x0100)

    # -- process helpers --------------------------------------------------------------

    def _process_tree_pids(self, root: int) -> set[int]:
        import ctypes
        kernel32 = ctypes.windll.kernel32

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

        snap = kernel32.CreateToolhelp32Snapshot(0x2, 0)
        if snap == -1:
            return {root}
        parent_map: dict[int, int] = {}
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        try:
            if kernel32.Process32First(snap, ctypes.byref(entry)):
                while True:
                    parent_map[entry.th32ProcessID] = entry.th32ParentProcessID
                    if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                        break
        finally:
            kernel32.CloseHandle(snap)
        tree = {root}
        changed = True
        while changed:
            changed = False
            for pid, parent in parent_map.items():
                if pid not in tree and parent in tree:
                    tree.add(pid)
                    changed = True
        return tree

    @staticmethod
    def _process_image(pid: int) -> Optional[str]:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        try:
            buf = ctypes.create_unicode_buffer(260)
            size = ctypes.c_ulong(260)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return buf.value
            return None
        finally:
            kernel32.CloseHandle(handle)


def create_app_embedder() -> AppEmbedder:
    return Win32AppEmbedder() if os.name == "nt" else NullAppEmbedder()