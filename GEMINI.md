# Claude Usage Indicator

A lightweight system tray application for Linux (Ubuntu/GNOME) that displays real-time Claude API usage and token utilization.

## Project Overview

*   **Purpose:** Provides a persistent visual indicator of Claude API usage (5-hour and 7-day windows) in the system tray.
*   **Technologies:** Python 3, GTK 3 (via PyGObject), Cairo (for dynamic icon generation), and standard library `urllib` for API requests.
*   **Architecture:**
    *   `indicator/`: Core package containing logic.
    *   `indicator/api.py`: Handles OAuth token reading from `~/.claude/.credentials.json` and fetching usage data from Anthropic's API.
    *   `indicator/config.py`: Centralized configuration for paths, API URLs, and shared logging.
    *   `indicator/icons.py`: Uses Cairo to render circular progress arcs as PNG icons stored in `assets/`.
    *   `indicator/theme.py`: Defines color schemes, CSS for progress bars, and usage thresholds (OK < 70%, Warning 70-90%, Critical >= 90%).
    *   `indicator/tray.py`: Implements the `Gtk.StatusIcon` tray behavior and background polling.
    *   `indicator/window.py`: Implements the popup window shown when clicking the tray icon.

## Building and Running

### System Dependencies

The application requires Python 3 and GTK 3 introspection libraries. On Ubuntu/Debian:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 python3-cairo gir1.2-appindicator3-0.1
```

### Running the Application

Execute the main script:

```bash
python3 claude_usage_indicator.py &
```

*Note: Requires an active graphical session (DISPLAY environment variable set).*

### Installation (Autostart)

To make the indicator start automatically on login:

```bash
./install.sh
```

This creates a `.desktop` entry in `~/.config/autostart/`.

## Development Conventions

*   **Logging:** All logs are written to `claude_usage_indicator.log` in the project root and to `stdout`.
*   **API Polling:** Usage data is polled every 30 minutes (`POLL_INTERVAL`). A 60-second cooldown is enforced on manual refreshes (clicking the tray icon).
*   **UI Safety:** Always use `GLib.idle_add` when updating GTK widgets from background threads or callbacks to ensure thread safety.
*   **Icon Rendering:** Icons are generated once at startup in the `assets/` directory. They use representative values (45%, 80%, 95%) to indicate the current tier, while exact percentages are shown in tooltips and the popup window.
*   **Error Handling:** API errors (like 429 Rate Limiting) are logged, and the application continues to display cached data.

## Key Files

*   `claude_usage_indicator.py`: The entry point that initializes icons and starts the tray application.
*   `install.sh`: Installation script for setting up autostart.
*   `CLAUDE.md`: Original development notes and architectural details.
*   `indicator/config.py`: Single source of truth for all paths and constants.
