# BrowsRrr

An infinite-canvas multi-monitor workspace that embeds external Windows applications as resizable subwindows, with a native-feel UI and a Start-Menu-indexed photo-reel app launcher.

## Purpose

BrowsRrr turns your entire monitor array into a single infinite canvas. External applications — native Win32 (32- and 64-bit), UWP/packaged apps, games, editors — launch directly into the workspace as live subwindows that resize, minimize, and move like first-class citizens. A right-click app reel searches every app on the computer (same source as the Start Menu) with real-time filtering, and remembers apps you've launched through it.

## Design Philosophy

- Native-smooth windowing — main-window resize/move driven by WM_NCHITTEST / WM_SIZING / WM_MOVING, clamped to the logical bounds of the connected monitor layout.
- Silent embed-first launch — apps start with SW_HIDE / CREATE_NO_WINDOW; a WinEvent hook adopts windows at creation, with process-tree and snapshot fallbacks.
- Start-Menu-parity search — the reel indexes Get-StartApps (Win32 + packaged), resolves bare exe names via App Paths, and shows reel-launched recents when idle.
- Differential spanning — floating min/max/close clusters appear on any monitor where the title bar is clipped.
- Verification + self-blocking — a 2.5s check verifies the embed stayed parented with no stray windows; failures auto-kill, block the command, and remove it from the reel.
- Architecture-safe Win32 layer — all HWND/pointer calls use typed prototypes (GetWindowLongPtrW, LONG_PTR) so 32-bit and 64-bit apps both embed correctly.

## File Structure

    main.py                         Top-level launcher
    build_executable.bat            PyInstaller build script
    repair_shortcuts.py             Utility: restore corrupt .lnk files from Start Menu
    check_shortcuts.py              Utility: report corrupt vs intact .lnk files
    browsrrr/
        app.py                      Entry point / QApplication bootstrap
        workspace_window.py         Main window: native resize, taskbar, reel, session
        workspace.py                Infinite canvas + subwindow accommodation
        sub_window.py               SubWindow shell: borders, embed mgmt, verification
        title_bar.py                Custom title bar + floating control clusters
        app_reel.py                 Photo-reel launcher: recents + live index search
        app_catalog.py              Get-StartApps index, recents, blocklist, icons
        win32_api.py                Typed 32/64-bit Win32 prototypes + known folders
        win32_embedder.py           HWND adoption, WinEvent hook, stray detection
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
| Silent launch + HWND reparenting (32- and 64-bit apps) | Done |
| WinEvent-hook instant adoption + process-tree/snapshot fallbacks | Done |
| Stray-window detection, auto-kill, permanent blocklist | Done |
| App reel: Start-Menu index (Get-StartApps) with live search | Done |
| App reel idle list = recents launched via the reel | Done |
| Typed Win32 API layer (win32_api.py) | Done |
| Downloads manager (Chromium) | Done |
| Session save/restore (geometry + subwindows) | Done |
| Code editor + AI panel subwindows | Done |
| Shortcut repair/diagnostic utilities | Done |
| PyInstaller build (build_executable.bat) | Done |

## Next Steps

1. Fuzzy reel search — rank results like the Start Menu (prefix/word-boundary matching, usage weighting).
2. Subwindow tiling/snapping — drag to canvas edges to snap halves/quarters.
3. Persistent workspace zones — named subwindow layouts for quick recall.
4. Multi-workspace tabs — switchable canvases sharing the same monitor span.
5. Embedded-app IPC — reliable clipboard/keystroke forwarding to embedded apps.
6. Linux/macOS embedders — XEmbed / NSView reparenting equivalents.
7. Accessibility — focus rings, screen-reader labels, high-contrast palette.

## Running

    pip install -r requirements.txt
    python main.py

## Building

    build_executable.bat

Output: dist\BrowsRrr\BrowsRrr.exe