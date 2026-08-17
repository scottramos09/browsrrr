from __future__ import annotations

import ctypes
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from . import win32_api as api

RECENT_CAP = 12
INDEX_CAP = 1000
SHGFI_ICON = 0x00000100
SHGFI_PIDL = 0x00000008


@dataclass(frozen=True)
class AppEntry:
    name: str
    path: str
    lnk: str = ""


def recents_file() -> Path:
    return Path.home() / ".browsrrr" / "recent_apps.json"


def catalog_file() -> Path:
    return Path.home() / ".browsrrr" / "app_catalog.json"


def blocked_file() -> Path:
    return Path.home() / ".browsrrr" / "unembeddable_apps.json"


def load_entries(path: Path) -> list[AppEntry]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [AppEntry(**item) for item in data if set(item) >= {"name", "path"}]


def save_entries(path: Path, entries: list[AppEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(e) for e in entries], indent=2), encoding="utf-8")


def load_blocked(path: Optional[Path] = None) -> set[str]:
    p = path or blocked_file()
    if not p.exists():
        return set()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    return {str(x).lower() for x in data if isinstance(x, str)}


def block_entry(command: str, path: Optional[Path] = None) -> None:
    p = path or blocked_file()
    blocked = load_blocked(p)
    blocked.add(command.strip().lower())
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sorted(blocked), indent=2), encoding="utf-8")


def record_recent(command: str, file: Optional[Path] = None, name: Optional[str] = None) -> None:
    """Stores a recent launch with its real display name (Start-Menu parity)."""
    path = file or recents_file()
    entry = AppEntry(name=name or Path(command.strip('"')).stem, path=command)
    entries = [e for e in load_entries(path) if e.path != entry.path]
    entries.insert(0, entry)
    save_entries(path, entries[:RECENT_CAP])


# ---------------------------------------------------------------- Start-Menu index

def _app_paths_full(exe_name: str) -> Optional[str]:
    """Resolves bare exe names (e.g. notepad.exe) via the App Paths registry key."""
    import winreg

    for hkey in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            key = winreg.OpenKey(
                hkey, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}"
            )
        except OSError:
            continue
        try:
            value, _ = winreg.QueryValueEx(key, "")
            if value:
                return value
        except OSError:
            pass
        finally:
            winreg.CloseKey(key)
    return None


def scan_all_apps(limit: int = INDEX_CAP) -> list[AppEntry]:
    """The same app list the Start Menu uses (Win32 + packaged), via Get-StartApps.

    No per-app allowlists: redirector stubs are handled at runtime by reactive
    AUMID discovery in the embedder, so bare exe names resolve normally here.
    """
    if os.name != "nt":
        return []
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "Get-StartApps | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        data = json.loads(proc.stdout)
    except Exception:
        return []
    if isinstance(data, dict):
        data = [data]

    entries: list[AppEntry] = []
    seen: set[str] = set()
    for item in data:
        name = (item.get("Name") or "").strip()
        appid = (item.get("AppID") or "").strip()
        if not name or not appid:
            continue
        if appid.lower().endswith(".exe") and ":\\" not in appid:
            full = _app_paths_full(appid)
            if full:
                appid = full
        if appid.lower().endswith(".exe") or ":\\" in appid:
            path = appid
        else:
            path = f"explorer.exe shell:AppsFolder\\{appid}"
        key = path.lower()
        if key in seen:
            continue
        seen.add(key)
        entries.append(AppEntry(name=name, path=path))
        if len(entries) >= limit:
            break
    entries.sort(key=lambda e: e.name.lower())
    return entries


# ---------------------------------------------------------------- Icons

_icon_cache: dict[str, object] = {}


def _aumid_from_command(path: str) -> Optional[str]:
    low = path.lower()
    marker = "shell:appsfolder\\"
    idx = low.find(marker)
    if idx == -1:
        return None
    return path[idx + len(marker):].strip() or None


def _icon_from_aumid(aumid: str, size: int):
    """Real package icon via the AppsFolder PIDL (what the Start Menu renders)."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap

    try:
        pidl = ctypes.c_void_p()
        hr = api.shell32.SHParseDisplayName(f"shell:AppsFolder\\{aumid}", None,
                                            ctypes.byref(pidl), 0, None)
        if hr != 0 or not pidl:
            return None
        info = api.SHFILEINFO()
        ok = api.shell32.SHGetFileInfoW(
            ctypes.cast(pidl, ctypes.c_wchar_p), 0,
            ctypes.byref(info), ctypes.sizeof(info), SHGFI_ICON | SHGFI_PIDL,
        )
        if not ok or not info.hIcon:
            return None
        from_hicon = getattr(QPixmap, "fromWinHICON", None) or getattr(QPixmap, "fromWinHIcon", None)
        raw = from_hicon(info.hIcon) if from_hicon else None
        api.user32.DestroyIcon(info.hIcon)
        if raw is not None and not raw.isNull():
            return raw.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return None
    except Exception:
        return None


def app_icon(path: str, size: int = 48):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap

    key = f"{path}:{size}"
    if key in _icon_cache:
        return _icon_cache[key]

    pix = None
    if os.name == "nt":
        aumid = _aumid_from_command(path)
        if aumid:
            pix = _icon_from_aumid(aumid, size)
        elif ":\\" in path:
            try:
                info = api.SHFILEINFO()
                ok = api.shell32.SHGetFileInfoW(
                    path, 0, ctypes.byref(info), ctypes.sizeof(info), SHGFI_ICON
                )
                if ok and info.hIcon:
                    from_hicon = getattr(QPixmap, "fromWinHICON", None) or getattr(QPixmap, "fromWinHIcon", None)
                    raw = from_hicon(info.hIcon) if from_hicon else None
                    api.user32.DestroyIcon(info.hIcon)
                    if raw is not None and not raw.isNull():
                        pix = raw.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            except Exception:
                pix = None

    _icon_cache[key] = pix
    return pix