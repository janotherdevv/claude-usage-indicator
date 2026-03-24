#!/usr/bin/env bash
set -euo pipefail

echo "Installing Claude Usage Watcher..."
echo ""

# Ensure system dependencies are present before pip install
SYS_DEPS=(python3-gi python3-gi-cairo python3-cairo gir1.2-gtk-3.0 gir1.2-notify-0.7)
MISSING=()
for pkg in "${SYS_DEPS[@]}"; do
    if ! dpkg -s "$pkg" &>/dev/null; then
        MISSING+=("$pkg")
    fi
done
if [ ${#MISSING[@]} -gt 0 ]; then
    echo "Installing system dependencies: ${MISSING[*]}"
    sudo apt install -y "${MISSING[@]}"
fi

# Install the Python package using pipx (isolated env with access to system GTK bindings)
echo "Installing Python package..."
if command -v pipx &>/dev/null; then
    pipx install . --system-site-packages --force
else
    echo "pipx not found, installing it first..."
    sudo apt install -y pipx
    pipx install . --system-site-packages --force
fi

# Run the built-in installer (checks deps, generates icons, creates autostart)
# Use python -m as fallback in case ~/.local/bin is not yet in PATH
claude-usage-watcher --install 2>/dev/null || python3 -m watcher --install
