#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/claude-usage-indicator.desktop"

echo "Installing Claude Usage Indicator..."

# Check dependencies
if ! python3 -c "import gi; gi.require_version('AppIndicator3', '0.1'); from gi.repository import AppIndicator3" 2>/dev/null; then
    echo "Missing dependencies. Installing..."
    sudo apt install -y python3-gi gir1.2-appindicator3-0.1 gir1.2-gtk-3.0
fi

chmod +x "$SCRIPT_DIR/claude_usage_indicator.py"

mkdir -p "$AUTOSTART_DIR"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Claude Usage Indicator
Exec=python3 $SCRIPT_DIR/claude_usage_indicator.py
Icon=$SCRIPT_DIR/assets/icon_ok.png
Comment=Shows Claude API usage in the system tray
Categories=Utility;
StartupNotify=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
EOF

echo "Autostart entry created: $DESKTOP_FILE"
echo ""
echo "To start now:  python3 $SCRIPT_DIR/claude_usage_indicator.py &"
echo "It will auto-start on next login."
