# BrowsRrr

An infinite-canvas multi-monitor workspace that embeds external Windows applications as resizable subwindows, with a native-feel UI and a Start-Menu-indexed photo-reel app launcher.

## Purpose

BrowsRrr turns your entire monitor array into a single infinite canvas. External applications — native Win32 (32- and 64-bit), self-hosted MSIX apps, frame-hosted XAML/UWP apps, Electron apps, and System32 redirector stubs — launch into the workspace as live subwindows that resize, minimize, and move like first-class citizens. A right-click app reel searches every app on the computer (Start Menu index) with token/initials filtering, shows real package icons, and remembers apps you've launched through it under their real Start-Menu names.

## Design Philosophy

- Two embedding strategies, chosen per app at ingest time:
  - Reparented (SetParent into WS_CHILD) for ordinary Win32 HWNDs and self-hosted MSIX apps (Paint, Terminal).
  - Positional overlay (never reparented) for CoreWindow/XAML UWP apps whose composition engine crashes under SetParent (Calculator, Clock).
- One canonical main-window test — visible, captioned, not a child, not a tool window, unowned — used by every matching path; no per-app tuning.
- Adopt one primary window, then stop — universal per subwindow.
- Three-tier app identity resolution — own-process AUMID, CoreWindow-child process AUMID, window property store; matching always by resolved AUMID string.
- Frame-host-safe teardown — closing a subwindow kills the tenant app process, never the shared ApplicationFrameHost.
- User-file safety — the app never opens Desktop shortcuts; every .lnk read is SHA-256 mutation-guarded and refused on any change.
- STA COM before Qt loads — initialized at the top of main.py before any PySide6 import.
- Reactive packaged discovery with process-tree fallback — no hardcoded lists.
- Native-smooth windowing — WM_NCHITTEST / WM_SIZING / WM_MOVING driven, clamped to logical monitor bounds.
- Silent embed-first launch — SW_HIDE / CREATE_NO_WINDOW, WinEvent-hook adoption, non-blocking GUI.
- Start-Menu-parity search and recents — Get-StartApps + Start-Menu sweep; token + initials matching.
- Adaptive verification — retry budget, post-adoption force-redraw, AUMID-aware stray kill, blocklist routing to external mode.
- Differential spanning — floating control clusters on clipped monitors.
- Architecture-safe Win32 layer — typed prototypes throughout.

## File Structure

    main.py                         Launcher: STA COM init before Qt, then run()
    build_executable.bat            PyInstaller build script
    repair_shortcuts.py             Utility: rebuild Desktop shortcuts from Start Menu
    check_shortcuts.py              Utility: report corrupt vs intact .lnk files
    browsrrr/
        app.py                      QApplication bootstrap + shutdown COM balance
        workspace_window.py         Main window: native resize, taskbar, reel, session
        workspace.py                Infinite canvas + subwindow accommodation
        sub_window.py               SubWindow shell: reparented + positional embedding
        title_bar.py                Custom title bar + floating control clusters
        app_reel.py                 Photo-reel launcher: recents + token/initials search
        app_catalog.py              App index (Start Menu only), recents, guarded icons
        win32_api.py                Typed 32/64-bit Win32 prototypes + known folders
        win32_embedder.py           Canonical predicate, adoption, AUMID resolution,
                                    positional overlay primitives
        web_subwindow.py            Chromium web subwindow content
        code_editor_widget.py       Built-in code editor
        code_runner.py              Code execution runtime
        ai_panel.py / ai_service.py / ai_worker.py   AI stack
        config.py / session.py      Settings + session persistence
        settings_dialog.py          Settings UI
        monitor_spanner.py / qt_monitors.py / domain.py   Multi-monitor math
        canvas.py / urls.py / ollama.py   Drawing, URLs, local AI
    tests/                          Pytest suite

## Current Status

| Feature | State |
|---|---|
| Frameless main window, native resize/move, monitor-bound clamping | Done |
| Differential spanning + floating control clusters | Done |
| Subwindow border resize, title-bar drag, minimize-to-taskbar | Done |
| Canonical is_main_window predicate shared by all matching paths | Done |
| Universal adopt-one-primary-then-stop | Done |
| STA COM pre-Qt init | Done |
| CoreWindow-child AUMID fallback for frame-hosted UWP | Done |
| Positional overlay embedding for CoreWindow apps | Done |
| Frame-host-safe process teardown | Done |
| Reactive discovery + process-tree fallback | Done |
| Non-blocking adoption (hook + poll, no GUI stalls) | Done |
| AppsFolder PIDL icons (Start-Menu parity) | Done |
| Recents with real Start-Menu display names | Done |
| Index sweep limited to Start Menu roots (Desktop never touched) | Done |
| SHA-256 mutation guard on every .lnk read | Done |
| Token + initials reel search | Done |
| Stub/WindowsApps routing: external only for genuinely un-embeddable forms | Done |
| Adaptive verification with retry budget | Done |
| Stray detection, AUMID-aware auto-kill, blocklist routing | Done |
| Downloads manager (Chromium) | Done |
| Session save/restore | Done |
| Code editor + AI panel subwindows | Done |
| Shortcut repair/diagnostic utilities | Done |
| PyInstaller build | Done |

## Known Platform Limitations

- Windows' composition engine cannot reparent CoreWindow/XAML apps; those use positional overlay embedding (own title bar visible inside the content area; not clipped by overlapping subwindows).
- WindowsApps targets and shell:AppsFolder apps that refuse all embedding run as normal external windows.
- Genuine embed failures are killed, blocked, and routed to external mode.

## Next Steps

1. Remove temporary [diag] tracing once the matrix is clean.
2. Overlay polish: borderless presentation for positional apps where safe.
3. Subwindow tiling/snapping.
4. Persistent workspace zones.
5. Multi-workspace tabs.
6. UWP streaming embed (DX capture) as a third strategy.
7. Embedded-app IPC (clipboard/keystrokes).
8. Linux/macOS embedders.
9. Accessibility pass.

## Running

    pip install -r requirements.txt
    python main.py

## Building

    build_executable.bat

Output: dist\BrowsRrr\BrowsRrr.exe