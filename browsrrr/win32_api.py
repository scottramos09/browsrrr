from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32
ole32 = ctypes.windll.ole32

LONG_PTR = ctypes.c_ssize_t
HWND = wintypes.HWND
INVALID_HANDLE = ctypes.c_void_p(-1).value

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, wintypes.LPARAM)
WINEVENTPROC = ctypes.WINFUNCTYPE(
    None, ctypes.c_void_p, wintypes.DWORD, HWND,
    ctypes.c_long, ctypes.c_long, wintypes.DWORD, wintypes.DWORD,
)


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_byte * 8),
    ]


class SHFILEINFO(ctypes.Structure):
    _fields_ = [
        ("hIcon", ctypes.c_void_p),
        ("iIcon", ctypes.c_int),
        ("dwAttributes", ctypes.c_ulong),
        ("displayName", ctypes.c_wchar * 260),
        ("typeName", ctypes.c_wchar * 80),
    ]


def make_guid(text: str) -> GUID:
    text = text.strip("{}")
    a, b, c, d = text.split("-", 3)
    d_bytes = bytes.fromhex(d.replace("-", ""))
    g = GUID()
    g.Data1 = int(a, 16)
    g.Data2 = int(b, 16)
    g.Data3 = int(c, 16)
    g.Data4 = (ctypes.c_byte * 8)(*d_bytes)
    return g


# -- 32/64-bit safe prototypes ------------------------------------------------

user32.SetParent.restype = HWND
user32.SetParent.argtypes = [HWND, HWND]
user32.GetParent.restype = HWND
user32.GetParent.argtypes = [HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindow.argtypes = [HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [HWND]

if hasattr(user32, "GetWindowLongPtrW"):
    GetWindowLongPtr = user32.GetWindowLongPtrW
    SetWindowLongPtr = user32.SetWindowLongPtrW
else:  # 32-bit Python: Ptr variants are not exported
    GetWindowLongPtr = user32.GetWindowLongW
    SetWindowLongPtr = user32.SetWindowLongW
GetWindowLongPtr.restype = LONG_PTR
GetWindowLongPtr.argtypes = [HWND, ctypes.c_int]
SetWindowLongPtr.restype = LONG_PTR
SetWindowLongPtr.argtypes = [HWND, ctypes.c_int, LONG_PTR]

user32.SetWindowPos.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [HWND, HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.MoveWindow.restype = wintypes.BOOL
user32.MoveWindow.argtypes = [HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]
user32.ShowWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [HWND, ctypes.c_int]
user32.EnumWindows.restype = wintypes.BOOL
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
user32.SendMessageW.restype = LONG_PTR
user32.SendMessageW.argtypes = [HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.RedrawWindow.restype = wintypes.BOOL
user32.RedrawWindow.argtypes = [HWND, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
user32.DestroyIcon.restype = wintypes.BOOL
user32.DestroyIcon.argtypes = [ctypes.c_void_p]

user32.SetWinEventHook.restype = ctypes.c_void_p
user32.SetWinEventHook.argtypes = [
    wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE, WINEVENTPROC,
    wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
]
user32.UnhookWinEvent.restype = wintypes.BOOL
user32.UnhookWinEvent.argtypes = [ctypes.c_void_p]

kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
]
kernel32.TerminateProcess.restype = wintypes.BOOL
kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.Process32First.restype = wintypes.BOOL
kernel32.Process32First.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
kernel32.Process32Next.restype = wintypes.BOOL
kernel32.Process32Next.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
kernel32.GetApplicationUserModelId.restype = ctypes.c_long
kernel32.GetApplicationUserModelId.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(ctypes.c_ulong), wintypes.LPWSTR,
]

ole32.CoInitializeEx.restype = ctypes.c_long
ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
ole32.CoUninitialize.restype = None
ole32.CoUninitialize.argtypes = []
ole32.CLSIDFromString.restype = ctypes.c_long
ole32.CLSIDFromString.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(GUID)]
ole32.CoCreateInstance.restype = ctypes.c_long
ole32.CoCreateInstance.argtypes = [
    ctypes.POINTER(GUID), ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p),
]
ole32.CoTaskMemFree.restype = None
ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
ole32.PropVariantClear.restype = ctypes.c_long
ole32.PropVariantClear.argtypes = [ctypes.c_void_p]

shell32.SHGetFileInfoW.restype = LONG_PTR
shell32.SHGetFileInfoW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(SHFILEINFO), wintypes.UINT, wintypes.UINT,
]
shell32.SHGetKnownFolderPath.restype = ctypes.c_long
shell32.SHGetKnownFolderPath.argtypes = [
    ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE,
    ctypes.POINTER(ctypes.c_wchar_p),
]
shell32.SHParseDisplayName.restype = ctypes.c_long
shell32.SHParseDisplayName.argtypes = [
    wintypes.LPCWSTR, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
    wintypes.ULONG, ctypes.POINTER(wintypes.ULONG),
]
shell32.SHGetPropertyStoreForWindow.restype = ctypes.c_long
shell32.SHGetPropertyStoreForWindow.argtypes = [
    HWND, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p),
]


# -- known folders --------------------------------------------------------------

def known_folder_path(text: str) -> Path | None:
    guid = make_guid(text)
    ptr = ctypes.c_wchar_p()
    hr = shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(ptr))
    if hr == 0 and ptr.value:
        value = ptr.value
        ole32.CoTaskMemFree(ptr)
        return Path(value)
    return None


def desktop_folder_paths() -> list[Path]:
    """Exact current-user + public desktop paths, per the shell."""
    out: list[Path] = []
    for guid in (
        "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",  # FOLDERID_Desktop
        "{C4AA340D-F20F-4D0F-A31C-CB5DFE1B2698}",  # FOLDERID_CommonDesktop
    ):
        path = known_folder_path(guid)
        if path and path not in out:
            out.append(path)
    return out