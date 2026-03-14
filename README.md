# Claude Usage Indicator

A lightweight system tray application for Linux (Ubuntu/GNOME) that displays real-time Claude API usage and token utilization.

![Window](claude-code-usage-window.png)

## Features

*   **Linux Desktop Native:** Specifically designed for Linux environments with GTK 3 and AppIndicator support.
*   **Real-time Monitoring:** Displays Claude API usage for both 5-hour and 7-day windows.
*   **Dynamic Tray Icon:** Circular progress arcs rendered in real-time that change color based on usage (OK < 70%, Warning 70-90%, Critical >= 90%).
*   **Detailed Popup:** Click the tray icon to see exact percentages, reset times, and any API errors.
*   **Resource Efficient:** Written in Python using Cairo for lightweight vector rendering.
*   **Standardized Paths:** Follows XDG standards for logs (`~/.local/share`) and cache (`~/.cache`).

## Prerequisites

The application requires Python 3 and GTK 3 introspection libraries. On Ubuntu/Debian, install them using:

```bash
sudo apt update
sudo apt install python3-gi gir1.2-gtk-3.0 python3-cairo gir1.2-appindicator3-0.1
```

## Configuration

The application reads your Claude API credentials from `~/.claude/.credentials.json`. 

Ensure the file exists with the following structure:

```json
{
  "claudeAiOauth": {
    "accessToken": "YOUR_ACCESS_TOKEN",
    "expiresAt": 1741910400000
  }
}
```

*Note: `expiresAt` is optional but recommended for token validity checks (timestamp in milliseconds).*

## Installation

The easiest way to install and configure the application is using the provided installation script:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/claude-usage-indicator.git
    cd claude-usage-indicator
    ```

2.  **Run the installation script:**
    This script installs the Python package, ensures system dependencies are met, and sets up the autostart entry.
    ```bash
    chmod +x install.sh
    ./install.sh
    ```

## Usage

### Command Line
Once installed, you can start the indicator from your terminal:
```bash
claude-usage-indicator &
```

### Automatic Start
The installation script creates a `.desktop` entry in `~/.config/autostart/`, so the application will start automatically every time you log in to your desktop environment.

### Monitoring Logs
Logs are managed via standard RotatingFileHandlers. You can monitor activity with:
```bash
tail -f ~/.local/share/claude-usage-indicator/logs/indicator.log
```

## Development & Structure

The project is structured as a standard Python package using `hatchling` as the build system.

### Key Files
*   `pyproject.toml`: Package metadata and entry points.
*   `indicator/`: Main package containing the application logic.
    *   `tray.py`: Application entry point and tray logic.
    *   `api.py`: Anthropic API integration.
    *   `icons.py`: Dynamic Cairo-based icon rendering.
    *   `config.py`: Centralized XDG-compliant path management.
*   `install.sh`: System-level installation and autostart setup.

### Editable Install
For development, you can install the package in editable mode:
```bash
pip install -e .
```

## License

This project is licensed under the [MIT License](LICENSE).
