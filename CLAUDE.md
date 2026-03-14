# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

```bash
python3 claude_usage_indicator.py &
```

Requires a graphical session (DISPLAY must be set). No virtual environment needed — uses only stdlib + system GTK bindings + pycairo.

## System dependencies

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 python3-cairo
```

## Installing autostart on login

```bash
./install.sh
```

This copies a `.desktop` entry to `~/.config/autostart/`.

## Project structure

```
claude-usage-indicator/
├── claude_usage_indicator.py   ← entry point
├── install.sh
├── assets/                     ← PNGs generated at startup (git-ignored)
│   ├── icon_ok.png
│   ├── icon_warn.png
│   └── icon_crit.png
└── indicator/                  ← Python package
    ├── config.py               ← paths, constants, shared logger
    ├── theme.py                ← tier thresholds, colors, CSS, icon paths
    ├── icons.py                ← Cairo PNG generation
    ├── api.py                  ← token reading, API fetch, time formatting
    ├── window.py               ← UsageWindow (popup UI)
    └── tray.py                 ← ClaudeIndicator (tray icon + polling)
```

## Architecture

**`indicator/config.py`** — single source of truth for all on-disk paths
- `PROJECT_ROOT` computed via `Path(__file__).parent.parent` — works regardless of cwd
- `CREDENTIALS_PATH`, `API_URL`, `POLL_INTERVAL`, `ASSETS_DIR`, `LOG_PATH`
- Configures the shared logger `"claude_usage"` (file + console, with timestamps)

**`indicator/theme.py`** — presentation policy
- `tier(utilization)` is the single source of truth for green/amber/red thresholds (< 70% / 70–90% / ≥ 90%)
- `arc_color()`, `bar_css()`, `icon_path_for()` — all indexed by tier

**`indicator/icons.py`** — Cairo rendering
- `generate_icons()` writes three 22×22 PNGs to `assets/` at startup
- Arc progress meter: 270° sweep, 3px stroke, transparent background, white track at 25% opacity
- `Gtk.StatusIcon` requires static files on disk — icons use fixed representative values (45/80/95%), actual percentages shown in tooltip and popup

**`indicator/api.py`** — data layer
- `read_token()` reads `~/.claude/.credentials.json` → `claudeAiOauth.accessToken`, checks `expiresAt`
- `fetch_usage(token)` — `GET https://api.anthropic.com/api/oauth/usage` with header `anthropic-beta: oauth-2025-04-20`, returns `five_hour.utilization` and `seven_day.utilization` as floats (0–100), logs result to file and console
- Known issue: endpoint returns HTTP 429 with `retry-after: 0` — silently ignored, cached data shown instead

**`indicator/tray.py`** — `ClaudeIndicator`
- Uses `Gtk.StatusIcon` — left-click opens popup, right-click shows menu (Quit only)
- Background polling via `GLib.timeout_add_seconds(1800)` — every 30 minutes, async (non-blocking)
- On-demand fetch on every left-click; 60-second cooldown prevents duplicate requests
- Single `_fetching` flag prevents concurrent fetches
- UI callbacks always via `GLib.idle_add` — never touch GTK widgets from background threads
- Popup positioning uses `Gdk.Display.get_monitor_at_point()` (multi-monitor aware)

**`indicator/window.py`** — `UsageWindow`
- Rebuilt on every left-click (previous window destroyed before creating new one)
- Opens immediately in loading state (pulsing bars) while fetch runs in background thread
- Updates in-place via `update()` when fetch completes
- Undecorated window, closes on focus-out, positioned adjacent to tray icon
- Two sections: large percentage label + colored `Gtk.ProgressBar` + reset time

## Logging

Logs written to `claude_usage_indicator.log` (project root, git-ignored) and to stdout.
Format: `2026-03-14 15:42:07  INFO  OK — 5h: 23.4%  7d: 8.1%`
