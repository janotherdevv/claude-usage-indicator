#!/usr/bin/env python3
"""Claude Usage Watcher — Ubuntu System Tray"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from watcher.tray import main

if __name__ == "__main__":
    main()
