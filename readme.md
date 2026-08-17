# BrowsRrr

An infinite-canvas multi-monitor workspace that embeds external Windows applications as resizable subwindows, with a native-feel UI and a Start-Menu-indexed photo-reel app launcher.

## Purpose

BrowsRrr turns your entire monitor array into a single infinite canvas. External applications — native Win32 (32- and 64-bit), packaged/UWP apps, Electron apps, and System32 redirector stubs — launch directly into the workspace as live subwindows that resize, minimize, and move like first-class citizens. A right-click app reel searches every app on the computer (same source as the Start Menu) with real-time filtering, shows real package icons, and remembers apps you've launched through it under their real Start-Menu names.

## Design Philosophy

- One canonical main-window test — a window is adoptable iff it is visible, captioned, not a child, not a tool window, and unowned. Every matching path (WinEvent hook, pid/exe poll, AUMID poll, reactive discovery) uses this same predicate; no per-app tuning.
- Adopt one primary window, then stop — universal per subwindow, regardless of which path found the winner.
- Native-smooth windowing — main-window resize/move driven by WM_NCHITTEST / WM_SIZING / WM_MOVING, clamped to the logical bounds of the connected monitor layout.
- Silent embed-first launch — apps start with SW_HIDE / CREATE_NO_WINDOW; a WinEvent hook adopts windows at creation; adoption never blocks the GUI thread.
- Reactive packaged discovery — exes that hand off to a packaged process are detected at runtime by probing new windows' AUMIDs; no hardcoded stub lists.
- AUMID-aware packaged-app handling — shell:AppsFolder commands parse into AppUserModelIDs; windows match via PKEY_AppUserModel_ID / GetApplicationUserModelId; icons resolve through the AppsFolder PIDL exactly like the Start Menu.
- COM-correct shell integration — CoInitializeEx runs on the main thread at startup so PIDL/icon/property-store calls succeed.
- Start-Menu-parity search and recents — the reel indexes Get-StartApps; recents store the real display name handed in at launch.
- Adaptive verification — embed attempts get a retry budget; genuine failures auto-kill strays and route future launches to external mode.
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
        app_catalog.py              Get-StartApps index, recents, blocklist, icons
        win32_api.py                Typed 32/64-bit Win32 prototypes + known folders
        win32_embedder.py           Canonical main-window predicate, adoption, hooks
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
| Canonical is_main_window predicate shared by all four matching paths | Done |
| Universal adopt-one-primary-then-stop across pid/exe and AUMID paths | Done |
| Reactive AUMID discovery replaces hardcoded stub allowlists | Done |
| Non-blocking adoption (WinEvent hook + poll loop, no GUI-thread stalls) | Done |
| Packaged-app icons via AppsFolder PIDL (Start-Menu parity) | Done |
| Main-thread COM init for shell icon/PIDL/property-store calls | Done |
| Recents with real Start-Menu display names | Done |
| Stub/WindowsApps routing: external only for genuinely un-embeddable forms | Done |
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

Windows' composition engine cannot reparent some hosted UIs (WindowsApps targets, shell:AppsFolder apps that refuse SetParent). Those run as normal external windows — the only way they render 100% correctly. Everything else embeds via the canonical predicate; genuine embed failures are killed, blocked, and routed to external mode.

## Next Steps

1. Run the five-app generalization matrix; remove temporary [diag] tracing once clean.
2. Fuzzy reel search — rank results like the Start Menu (prefix/word-boundary matching, usage weighting).
3. Subwindow tiling/snapping — drag to canvas edges to snap halves/quarters.
4. Persistent workspace zones — named subwindow layouts for quick recall.
5. Multi-workspace tabs — switchable canvases sharing the same monitor span.
6. UWP streaming embed — investigate DX surface capture (RDP-style) for apps that refuse reparenting.
7. Embedded-app IPC — reliable clipboard/keystroke forwarding to embedded apps.
8. Linux/macOS embedders — XEmbed / NSView reparenting equivalents.
9. Accessibility — focus rings, screen-reader labels, high-contrast palette.

## Running

    pip install -r requirements.txt
    python main.py

## Building

    build_executable.bat

Output: dist\BrowsRrr\BrowsRrr.exe