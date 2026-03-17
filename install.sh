#!/usr/bin/env bash
set -euo pipefail

echo "Installing Claude Usage Watcher..."
echo ""

# Install the Python package
echo "Installing Python package..."
python3 -m pip install . 2>/dev/null || python3 -m pip install . --break-system-packages

# Run the built-in installer (checks deps, generates icons, creates autostart)
claude-usage-watcher --install
