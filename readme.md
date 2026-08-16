# BrowsRrr

An infinite-canvas multi-monitor workspace that embeds external Windows applications as resizable subwindows, with a native-feel UI and photo-reel desktop-app launcher.

## Purpose

BrowsRrr is a frameless Qt workspace that turns your entire monitor array into a single infinite canvas. External applications — native Win32 apps, UWP/packaged apps, games, editors — are launched directly into the workspace as live subwindows that resize, minimize, and move like first-class citizens. A right-click app reel surfaces desktop shortcuts with real Windows icons and an indexed search field.

## Design Philosophy

- **Native-smooth windowing** — Main-window resize/move is driven by `WM_NCHITTEST`/`WM_SIZING`/`WM_MOVING`, clamped to the logical bounds of the connected monitor layout.
- **Silent embed-first launch** — External apps start with `SW_HIDE`/`CREATE_NO_WINDOW`; the first caption window (visible or hidden, in-process or descendant) is reparented into a Qt-owned frame ring before the user ever sees a stray desktop window.
- **Differential spanning** — When the window spans monitors of different heights, floating min/max/close clusters appear on each monitor where the title bar is clipped.
- **Verification + self-blocking** — A 2.5s grace period verifies the embed is still parented and not straying; failures auto-kill the process, block the command, and remove it from the reel permanently.

## File Structure
