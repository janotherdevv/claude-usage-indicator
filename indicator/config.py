import logging
from pathlib import Path

# Raíz del proyecto: indicator/config.py → indicator/ → raíz
PROJECT_ROOT = Path(__file__).parent.parent

CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"
API_URL = "https://api.anthropic.com/api/oauth/usage"
POLL_INTERVAL = 1800  # segundos (30 minutos)
ASSETS_DIR = PROJECT_ROOT / "assets"
LOG_PATH = PROJECT_ROOT / "claude_usage_indicator.log"

# Logger compartido — otros módulos lo obtienen con logging.getLogger("claude_usage")
_log = logging.getLogger("claude_usage")
_log.setLevel(logging.INFO)
_log.addHandler(logging.FileHandler(LOG_PATH, encoding="utf-8"))
_log.addHandler(logging.StreamHandler())
for _h in _log.handlers:
    _h.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
