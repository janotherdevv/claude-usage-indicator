#!/usr/bin/env bash
set -euo pipefail

echo "Installing Claude Usage Watcher..."
echo ""

# Install the Python package
echo "Installing Python package..."
python3 -m pip install . 2>/dev/null || python3 -m pip install . --break-system-packages

# Run the built-in installer (checks deps, generates icons, creates autostart)
# Use python -m as fallback in case ~/.local/bin is not yet in PATH
claude-usage-watcher --install 2>/dev/null || python3 -m watcher --install
