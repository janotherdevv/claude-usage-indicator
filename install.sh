#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/com.claudeusage.watcher.desktop"

echo "Installing Claude Usage Watcher..."

# Check dependencies
if ! python3 -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk" 2>/dev/null || ! python3 -c "import cairo" 2>/dev/null || ! python3 -c "import gi; gi.require_version('Notify', '0.7')" 2>/dev/null; then
    echo "Missing dependencies. Installing..."
    sudo apt install -y python3-gi gir1.2-gtk-3.0 python3-cairo gir1.2-notify-0.7
fi

# Install the package (non-editable so files are copied to user's site-packages)
echo "Installing Python package..."
python3 -m pip install . 2>/dev/null || python3 -m pip install . --break-system-packages

# Generate icons once so the desktop file has something to show
echo "Generating initial icons..."
python3 -c "from watcher.icons import generate_icons; generate_icons()"

chmod +x "$SCRIPT_DIR/claude_usage_watcher.py"

mkdir -p "$AUTOSTART_DIR"
EXEC_PATH="$(python3 -c "import sysconfig; print(sysconfig.get_path('scripts', 'posix_user'))")/claude-usage-watcher"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Claude Usage Watcher
Exec=$EXEC_PATH --autostart
Icon=$HOME/.cache/claude-usage-watcher/assets/icon_current.png
Comment=Shows Claude API usage in the system tray
Categories=Utility;
StartupNotify=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
EOF

echo "Autostart entry created: $DESKTOP_FILE"
echo ""
echo "To start now:  claude-usage-watcher &"
echo "It will auto-start on next login."
