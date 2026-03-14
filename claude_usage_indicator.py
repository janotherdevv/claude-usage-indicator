#!/usr/bin/env python3
"""Claude Usage Indicator — Ubuntu System Tray"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from indicator.tray import ClaudeIndicator

if __name__ == "__main__":
    app = ClaudeIndicator()
    app.run()
