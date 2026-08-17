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


def resolve_shortcut(lnk_path: str) -> Optional[str]:
    if os.name != "nt":
        return None
    try:
        ole32 = api.ole32
        clsid = api.make_guid("{00021401-0000-0000-C000-000000000046}")
        iid_link = api.make_guid("{000214F9-0000-0000-C000-000000000046}")
        iid_file = api.make_guid("{0000010B-0000-0000-C000-000000000046}")

        link = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(iid_link), ctypes.byref(link))
        if hr != 0 or not link:
            return None
        link_vt = ctypes.cast(link, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        qi = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(api.GUID), ctypes.POINTER(ctypes.c_void_p))(link_vt[0])
        release = ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(link_vt[2])

        persist = ctypes.c_void_p()
        if qi(link, ctypes.byref(iid_file), ctypes.byref(persist)) != 0:
            release(link)
            return None
        persist_vt = ctypes.cast(persist, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        load = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_ulong)(persist_vt[6])
        ok = load(persist, lnk_path, 0)
        release(persist)

        target = None
        if ok == 0:
            get_path = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong)(link_vt[3])
            buf = ctypes.create_unicode_buffer(260)
            if get_path(link, buf, 260, None, 0) == 0 and buf.value:
                target = buf.value
        release(link)
        return target
    except Exception:
        return None


def _shortcut_roots() -> list[Path]:
    roots = []
    if "PROGRAMDATA" in os.environ:
        roots.append(Path(os.environ["PROGRAMDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    roots.append(Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    roots.append(Path.home() / "Desktop")
    roots.append(Path.home() / "OneDrive" / "Desktop")
    return [r for r in roots if r.exists()]


def scan_all_apps(limit: int = INDEX_CAP) -> list[AppEntry]:
    """Get-StartApps plus Start-Menu/desktop shortcuts it misses (VS Code, OBS, ...)."""
    if os.name != "nt":
        return []
    entries: list[AppEntry] = []
    seen: set[str] = set()
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "Get-StartApps | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        data = json.loads(proc.stdout)
        if isinstance(data, dict):
            data = [data]
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
    except Exception:
        pass

    names = {e.name.lower() for e in entries}
    for root in _shortcut_roots():
        for lnk in sorted(root.rglob("*.lnk")):
            target = resolve_shortcut(str(lnk))
            if not target or not target.lower().endswith(".exe"):
                continue
            name = lnk.stem
            if name.lower() in names:
                continue
            names.add(name.lower())
            entries.append(AppEntry(name=name, path=target, lnk=str(lnk)))

    entries.sort(key=lambda e: e.name.lower())
    return entries[:limit]


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