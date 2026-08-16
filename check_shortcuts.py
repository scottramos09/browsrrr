import ctypes
from ctypes import wintypes
from pathlib import Path


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_byte * 8)]


def make_guid(t):
    t = t.strip("{}")
    a, b, c, d = t.split("-", 3)
    g = GUID()
    g.Data1, g.Data2, g.Data3 = int(a, 16), int(b, 16), int(c, 16)
    g.Data4 = (ctypes.c_byte * 8)(*bytes.fromhex(d.replace("-", "")))
    return g


ole32 = ctypes.windll.ole32
ole32.CoInitializeEx.restype = ctypes.c_long
ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
ole32.CLSIDFromString.restype = ctypes.c_long
ole32.CLSIDFromString.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(GUID)]
ole32.CoCreateInstance.restype = ctypes.c_long
ole32.CoCreateInstance.argtypes = [ctypes.POINTER(GUID), ctypes.c_void_p, wintypes.DWORD,
                                   ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]


def resolve(p):
    try:
        clsid = make_guid("{00021401-0000-0000-C000-000000000046}")
        iid_l = make_guid("{000214F9-0000-0000-C000-000000000046}")
        iid_f = make_guid("{0000010B-0000-0000-C000-000000000046}")
        link = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(iid_l), ctypes.byref(link))
        if hr != 0 or not link:
            return None
        vt = ctypes.cast(link, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        qi = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))(vt[0])
        rel = ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vt[2])
        persist = ctypes.c_void_p()
        if qi(link, ctypes.byref(iid_f), ctypes.byref(persist)) != 0:
            rel(link)
            return None
        pvt = ctypes.cast(persist, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        load = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_ulong)(pvt[6])
        ok = load(persist, str(p), 0)
        rel(persist)
        target = None
        if ok == 0:
            gp = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong)(vt[3])
            buf = ctypes.create_unicode_buffer(260)
            if gp(link, buf, 260, None, 0) == 0 and buf.value:
                target = buf.value
        rel(link)
        return target
    except Exception:
        return None


def main():
    ole32.CoInitializeEx(None, 2)
    for loc in [Path.home() / "Desktop", Path.home() / "OneDrive" / "Desktop",
                Path.home() / "OneDrive - Personal" / "Desktop"]:
        if not loc.exists():
            continue
        print("==", loc)
        ok = bad = 0
        for lnk in sorted(loc.glob("*.lnk")):
            t = resolve(lnk)
            if t:
                ok += 1
            else:
                bad += 1
                print(f"   CORRUPT: {lnk.name} ({lnk.stat().st_size} bytes)")
        print(f"   intact={ok} corrupt={bad}")

    sm = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    print("== Start Menu sample (first 10)")
    for lnk in sorted(sm.rglob("*.lnk"))[:10]:
        print("  ", lnk.name, "->", resolve(lnk))


if __name__ == "__main__":
    main()