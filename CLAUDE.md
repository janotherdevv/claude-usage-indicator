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

## Architecture

Single-file app (`claude_usage_indicator.py`) with three layers:

**Data layer** (`read_token`, `fetch_usage`)
- Token read from `~/.claude/.credentials.json` → `claudeAiOauth.accessToken`
- Token expiry checked via `expiresAt` (milliseconds epoch)
- API: `GET https://api.anthropic.com/api/oauth/usage` with header `anthropic-beta: oauth-2025-04-20`
- Returns `five_hour.utilization` and `seven_day.utilization` as floats (0–100)

**Tray layer** (`ClaudeIndicator`)
- Uses `Gtk.StatusIcon` — left-click opens popup directly, right-click shows menu (Quit only)
- Icon reflects the higher of the two utilization values: green <70%, amber 70–90%, red ≥90%
- `status_icon.set_tooltip_text()` shows live percentages
- Background polling via `GLib.timeout_add_seconds(1800)` — every 30 minutes, async (non-blocking)
- On-demand fetch on every left-click, regardless of poll timer
- Single `_fetching` flag prevents duplicate concurrent requests
- `_tier(utilization)` is the single source of truth for green/amber/red thresholds (used by icons, bar CSS, and arc colors)

**UI layer** (`UsageWindow`)
- Rebuilt on every left-click (previous window destroyed before creating new one)
- Opens immediately in loading state (pulsing bars) while fetch runs in background thread
- Updates in-place via `update()` when fetch completes (`GLib.idle_add`)
- Undecorated window, closes on focus-out, positioned adjacent to tray icon
- Two sections: large percentage label + colored `Gtk.ProgressBar` + reset time
- "Updated just now" timestamp at bottom

## Icons

Three 22×22 PNG files (`icon_ok.png`, `icon_warn.png`, `icon_crit.png`) generated with Cairo at startup via `_generate_icons()`. Arc progress meter design: 270° sweep, 3px stroke, transparent background, white track at 25% opacity.
