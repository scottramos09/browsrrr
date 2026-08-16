"""Repairs corrupted desktop .lnk files by restoring intact copies from the Start Menu.
Corrupted originals are moved to Desktop\\_corrupted_backup (nothing is deleted)."""
import ctypes
import os
import shutil
import sys
from pathlib import Path

CLSCTX_INPROC_SERVER = 0x1


def _guid(text):
    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                    ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_byte * 8)]
    text = text.strip("{}")
    a, b, c, d = text.split("-", 3)
    g = GUID()
    g.Data1 = int(a, 16)
    g.Data2 = int(b, 16)
    g.Data3 = int(c, 16)
    g.Data4 = (ctypes.c_byte * 8)(*bytes.fromhex(d.replace("-", "")))
    return g


def resolve(lnk_path: str):
    try:
        ole32 = ctypes.windll.ole32
        ole32.CoInitializeEx(None, 2)
        clsid = _guid("{00021401-0000-0000-C000-000000000046}")
        iid_link = _guid("{000214F9-0000-0000-C000-000000000046}")
        iid_file = _guid("{0000010B-0000-0000-C000-000000000046}")
        link = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(ctypes.byref(clsid), None, CLSCTX_INPROC_SERVER,
                                    ctypes.byref(iid_link), ctypes.byref(link))
        if hr != 0 or not link:
            return None
        vt = ctypes.cast(link, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        qi = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(vt[0])
        release = ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vt[2])
        persist = ctypes.c_void_p()
        if qi(link, ctypes.byref(iid_file), ctypes.byref(persist)) != 0:
            release(link)
            return None
        pvt = ctypes.cast(persist, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        load = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_ulong)(pvt[6])
        ok = load(persist, lnk_path, 0)
        release(persist)
        target = None
        if ok == 0:
            get_path = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p,
                                        ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong)(vt[3])
            buf = ctypes.create_unicode_buffer(260)
            if get_path(link, buf, 260, None, 0) == 0 and buf.value:
                target = buf.value
        release(link)
        return target
    except Exception:
        return None


def desktop_locations():
    home = Path.home()
    cands = [home / "Desktop", home / "OneDrive" / "Desktop",
             home / "OneDrive - Personal" / "Desktop"]
    seen, out = set(), []
    for c in cands:
        if c.exists():
            real = c.resolve()
            if real not in seen:
                seen.add(real)
                out.append(c)
    return out


def start_menu_roots():
    roots = []
    if "PROGRAMDATA" in os.environ:
        roots.append(Path(os.environ["PROGRAMDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    roots.append(Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return [r for r in roots if r.exists()]


def main():
    # 1. Build a map of intact Start Menu shortcuts by name.
    good = {}
    for root in start_menu_roots():
        for lnk in root.rglob("*.lnk"):
            if lnk.stem not in good and resolve(str(lnk)):
                good[lnk.stem.lower()] = lnk

    fixed, unresolved, healthy = [], [], 0
    for desktop in desktop_locations():
        backup = desktop / "_corrupted_backup"
        for lnk in sorted(desktop.glob("*.lnk")):
            if resolve(str(lnk)):
                healthy += 1
                continue
            backup.mkdir(exist_ok=True)
            shutil.move(str(lnk), str(backup / lnk.name))
            name = lnk.stem.lower()
            if name.endswith(" - shortcut"):
                name = name[: -len(" - shortcut")]
            repl = good.get(name) or good.get(lnk.stem.lower())
            if repl:
                shutil.copy(str(repl), str(lnk))
                fixed.append(lnk.name)
            else:
                unresolved.append(lnk.name)

    print(f"Healthy desktop shortcuts: {healthy}")
    print(f"Restored from Start Menu : {len(fixed)}")
    for f in fixed:
        print("  +", f)
    print(f"Still unresolved         : {len(unresolved)}")
    for u in unresolved:
        print("  ?", u, "  (restore via OneDrive Version History or recreate manually)")
    print("Corrupted originals saved in: Desktop\\_corrupted_backup")


if __name__ == "__main__":
    main()