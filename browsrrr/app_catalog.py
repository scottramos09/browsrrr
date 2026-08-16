from __future__ import annotations

import codecs
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

RECENT_CAP = 12
SCAN_LIMIT = 200
LNK_FALLBACK_CAP = 150


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


def record_recent(command: str, file: Optional[Path] = None) -> None:
    path = file or recents_file()
    entry = AppEntry(name=Path(command.strip('"')).stem, path=command)
    entries = [e for e in load_entries(path) if e.path != entry.path]
    entries.insert(0, entry)
    save_entries(path, entries[:RECENT_CAP])


# ---------------------------------------------------------------- Windows sources / COM

def _com_enter():
    import ctypes

    ole32 = ctypes.windll.ole32
    hr = ole32.CoInitializeEx(None, 2)
    return ole32, hr


def _com_exit(ole32, hr) -> None:
    if hr == 0:
        ole32.CoUninitialize()


def resolve_shortcut(lnk_path: str) -> Optional[str]:
    if os.name != "nt":
        return None
    try:
        import ctypes

        ole32, hr_init = _com_enter()
        try:
            GUID = ctypes.c_char * 16
            clsid, iid_link, iid_file = GUID(), GUID(), GUID()
            ole32.CLSIDFromString("{00021401-0000-0000-C000-000000000046}", clsid)
            ole32.CLSIDFromString("{000214F9-0000-0000-C000-000000000046}", iid_link)
            ole32.CLSIDFromString("{0000010B-0000-0000-C000-000000000046}", iid_file)

            link = ctypes.c_void_p()
            if ole32.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(iid_link), ctypes.byref(link)) != 0:
                return None
            link_vt = ctypes.cast(link, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]

            persist = ctypes.c_void_p()
            qi = ctypes.CFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))(link_vt[0])
            release = ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(link_vt[2])
            if qi(link, iid_file, ctypes.byref(persist)) != 0:
                release(link)
                return None

            persist_vt = ctypes.cast(persist, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
            load = ctypes.CFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_ulong)(persist_vt[6])
            ok = load(persist, lnk_path, 0)
            ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(persist_vt[2])(persist)

            target = None
            if ok == 0:
                get_path = ctypes.CFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong)(link_vt[3])
                buf = ctypes.create_unicode_buffer(260)
                if get_path(link, buf, 260, None, 0) == 0 and buf.value:
                    target = buf.value
            release(link)
            return target
        finally:
            _com_exit(ole32, hr_init)
    except Exception:
        return None


# ---------------------------------------------------------------- Desktop scan

def desktop_dirs() -> list[Path]:
    dirs: list[Path] = []
    public = os.environ.get("PUBLIC")
    if public:
        dirs.append(Path(public) / "Desktop")
    dirs.append(Path.home() / "Desktop")
    dirs.append(Path.home() / "OneDrive" / "Desktop")
    seen: set[Path] = set()
    out: list[Path] = []
    for d in dirs:
        if d.exists() and d not in seen:
            seen.add(d)
            out.append(d)
    return out


def scan_desktop_apps(limit: int = SCAN_LIMIT) -> list[AppEntry]:
    """Only the shortcuts that live on the user's desktop."""
    if os.name != "nt":
        return []
    entries: list[AppEntry] = []
    seen: set[str] = set()
    for d in desktop_dirs():
        for lnk in sorted(d.glob("*.lnk")):
            target = resolve_shortcut(str(lnk))
            if not target or not target.lower().endswith(".exe"):
                continue
            key = target.lower()
            if key in seen:
                continue
            seen.add(key)
            entries.append(AppEntry(name=lnk.stem, path=target, lnk=str(lnk)))
            if len(entries) >= limit:
                return entries
        for exe in sorted(d.glob("*.exe")):
            key = str(exe).lower()
            if key in seen:
                continue
            seen.add(key)
            entries.append(AppEntry(name=exe.stem, path=str(exe)))
            if len(entries) >= limit:
                return entries
    return entries


# ---------------------------------------------------------------- Icons

_icon_cache: dict[str, object] = {}


def app_icon(path: str, size: int = 48):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap

    key = f"{path}:{size}"
    if key in _icon_cache:
        return _icon_cache[key]

    pix = None
    if os.name == "nt" and ":\\" in path:
        try:
            import ctypes

            ole32, hr_init = _com_enter()
            try:
                class SHFILEINFO(ctypes.Structure):
                    _fields_ = [
                        ("hIcon", ctypes.c_void_p),
                        ("iIcon", ctypes.c_int),
                        ("dwAttributes", ctypes.c_ulong),
                        ("displayName", ctypes.c_wchar * 260),
                        ("typeName", ctypes.c_wchar * 80),
                    ]

                info = SHFILEINFO()
                ok = ctypes.windll.shell32.SHGetFileInfoW(path, 0, ctypes.byref(info), ctypes.sizeof(info), 0x100)
                if ok and info.hIcon:
                    from_hicon = getattr(QPixmap, "fromWinHICON", None) or getattr(QPixmap, "fromWinHICON", None)
                    raw = from_hicon(info.hIcon) if from_hicon else None
                    ctypes.windll.user32.DestroyIcon(info.hIcon)
                    if raw is not None and not raw.isNull():
                        pix = raw.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            finally:
                _com_exit(ole32, hr_init)
        except Exception:
            pix = None

    _icon_cache[key] = pix
    return pix