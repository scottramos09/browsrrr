import os
import sys

if os.name == "nt":
    # COM must be STA *before* PySide6/Qt loads; shell property-store APIs
    # (SHGetPropertyStoreForWindow) fail with E_NOINTERFACE on MTA threads.
    import ctypes

    _hr = ctypes.windll.ole32.CoInitializeEx(None, 2)  # COINIT_APARTMENTTHREADED
    print(f"[diag] main CoInitializeEx(STA) hr={_hr & 0xFFFFFFFF:#x}", flush=True)

from browsrrr.app import run

if __name__ == "__main__":
    sys.exit(run())