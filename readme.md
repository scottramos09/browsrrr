# BrowsRrr

An infinite-canvas multi-monitor workspace that embeds external Windows applications as resizable subwindows, with a native-feel UI and a Start-Menu-indexed photo-reel app launcher.

## Purpose

BrowsRrr turns your entire monitor array into a single infinite canvas. External applications — native Win32 (32- and 64-bit) and packaged/UWP apps — launch directly into the workspace as live subwindows that resize, minimize, and move like first-class citizens. A right-click app reel searches every app on the computer (same source as the Start Menu) with real-time filtering, shows real package icons, and remembers apps you've launched through it under their real Start-Menu names.

## Design Philosophy

- Native-smooth windowing — main-window resize/move driven by WM_NCHITTEST / WM_SIZING / WM_MOVING, clamped to the logical bounds of the connected monitor layout.
- Silent embed-first launch — apps start with SW_HIDE / CREATE_NO_WINDOW; a WinEvent hook adopts windows at creation, with process-tree, AUMID, and snapshot fallbacks.
- AUMID-aware packaged-app handling — shell:AppsFolder commands parse into AppUserModelIDs; windows match via PKEY_AppUserModel_ID / GetApplicationUserModelId; icons resolve through the AppsFolder PIDL exactly like the Start Menu.
- Stub-aware classification — Windows 11 System32 redirector stubs (mspaint.exe, notepad.exe, calc.exe) keep their packaged identity through index resolution; reactive AUMID adoption also catches stubs at runtime before any blacklist decision.
- COM-correct shell integration — CoInitializeEx runs on the main thread at startup so PIDL/icon calls succeed from the reel's paint path.
- Start-Menu-parity search and recents — the reel indexes Get-StartApps; recents store the real display name handed in at launch, never re-derived from paths.
- Adaptive verification — all launches get a retry budget plus a verify-time reactive adopt pass; failed embeds auto-kill strays (AUMID-aware) and route future launches to external mode.
- Differential spanning — floating min/max/close clusters appear on any monitor where the title bar is clipped.
- Architecture-safe Win32 layer — typed prototypes (GetWindowLongPtrW, LONG_PTR) so 32-bit and 64-bit apps both embed correctly.

## File Structure

    main.py                         Top-level launcher
    build_executable.bat            PyInstaller build script
    repair_shortcuts.py             Utility: restore corrupt .lnk files from Start Menu
    check_shortcuts.py              Utility: report corrupt vs intact .lnk files
    browsrrr/
        app.py                      Entry point: QApplication + main-thread COM init
        workspace_window.py         Main window: native resize, taskbar, reel, session
        workspace.py                Infinite canvas + subwindow accommodation
        sub_window.py               SubWindow shell: borders, embed mgmt, verification
        title_bar.py                Custom title bar + floating control clusters
        app_reel.py                 Photo-reel launcher: recents + live index search
        app_catalog.py              Get-StartApps index, stub table, recents, icons
        win32_api.py                Typed 32/64-bit Win32 prototypes + known folders
        win32_embedder.py           HWND adoption, WinEvent hook, AUMID matching
        web_subwindow.py            Chromium web subwindow content
        code_editor_widget.py       Built-in code editor
        code_runner.py              Code execution runtime
        ai_panel.py                 AI panel widget
        ai_service.py               AI agent service
        ai_worker.py                AI background worker
        config.py                   Settings persistence
        session.py                  Session save/restore
        settings_dialog.py          Settings UI
        monitor_spanner.py          Multi-monitor rect math
        qt_monitors.py              Qt screen enumeration
        domain.py                   Rect / Screen data classes
        canvas.py                   Drawing constants
        urls.py                     URL normalization
        ollama.py                   Local AI install helper
    tests/                          Pytest suite

## Current Status

| Feature | State |
|---|---|
| Frameless main window, native resize/move, monitor-bound clamping | Done |
| Multi-monitor differential spanning + floating control clusters | Done |
| Subwindow border resize, title-bar drag, minimize-to-taskbar | Done |
| Silent launch + HWND reparenting (32- and 64-bit Win32 apps) | Done |
| WinEvent-hook instant adoption + process-tree/snapshot fallbacks | Done |
| AUMID parsing + window/process AUMID matching for packaged apps | Done |
| Packaged-app icons via AppsFolder PIDL (Start-Menu parity) | Done |
| Main-thread COM init for shell icon/PIDL calls | Done |
| Recents with real Start-Menu display names | Done |
| System32 stub table preserves packaged identity in the index | Done |
| Verify-time reactive AUMID adoption (stub coverage at runtime) | Done |
| Adaptive embed verification with retry budget | Done |
| Stray-window detection, AUMID-aware auto-kill, blocklist routing | Done |
| App reel: complete Start-Menu index (Get-StartApps) with live search | Done |
| App reel idle list = recents launched via the reel | Done |
| Typed Win32 API layer (win32_api.py) | Done |
| Downloads manager (Chromium) | Done |
| Session save/restore (geometry + subwindows) | Done |
| Code editor + AI panel subwindows | Done |
| Shortcut repair/diagnostic utilities | Done |
| PyInstaller build (build_executable.bat) | Done |

## Known Platform Limitation

WindowsApps-folder packaged exes that refuse reparenting are detected and launched as normal windows (the only way they render 100% correctly). shell:AppsFolder packaged apps and System32 stubs embed via AUMID matching with adaptive grace; if verification ultimately fails they are killed, blocked, and routed to external mode.

## Next Steps

1. Fuzzy reel search — rank results like the Start Menu (prefix/word-boundary matching, usage weighting).
2. Subwindow tiling/snapping — drag to canvas edges to snap halves/quarters.
3. Persistent workspace zones — named subwindow layouts for quick recall.
4. Multi-workspace tabs — switchable canvases sharing the same monitor span.
5. UWP streaming embed — investigate DX surface capture (RDP-style) for stubborn packaged apps.
6. Embedded-app IPC — reliable clipboard/keystroke forwarding to embedded apps.
7. Linux/macOS embedders — XEmbed / NSView reparenting equivalents.
8. Accessibility — focus rings, screen-reader labels, high-contrast palette.

## Running

    pip install -r requirements.txt
    python main.py

## Building

    build_executable.bat

Output: dist\BrowsRrr\BrowsRrr.exe