# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

```bash
python3 claude_usage_indicator.py &
```

Requires a graphical session (DISPLAY must be set). No virtual environment needed — uses only stdlib + system GTK bindings.

## System dependencies

```bash
sudo apt install python3-gi gir1.2-appindicator3-0.1 gir1.2-gtk-3.0
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
- AppIndicator3 icon reflects the higher of the two utilization values: green <70%, yellow 70–90%, red ≥90%
- `indicator.set_title()` shows live percentages in the tooltip/label
- Polling via `GLib.timeout_add_seconds(300)` — integrated in the GTK event loop, no threads

**UI layer** (`UsageWindow`)
- Rebuilt on every "Show Usage" click (no persistent state)
- Two `Gtk.ProgressBar` widgets + reset times formatted in local timezone

## Icons

Three 22×22 PNG files (`icon_ok.png`, `icon_warn.png`, `icon_crit.png`) generated programmatically. If they need to be regenerated, the generation script is in the git history / plan notes.
