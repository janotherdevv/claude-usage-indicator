import logging
from datetime import datetime
from pathlib import Path

# Raíz del proyecto: indicator/config.py → indicator/ → raíz
PROJECT_ROOT = Path(__file__).parent.parent

CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"
API_URL = "https://api.anthropic.com/api/oauth/usage"
POLL_INTERVAL = 1800  # segundos (30 minutos)
ASSETS_DIR = PROJECT_ROOT / "assets"

# Configuración de Logs
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Archivo con la fecha del día: 2026-03-14.log
LOG_PATH = LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"

# Logger compartido — otros módulos lo obtienen con logging.getLogger("claude_usage")
_log = logging.getLogger("claude_usage")
_log.setLevel(logging.INFO)

# Handler estándar para el archivo (se crea uno nuevo si cambia el día al iniciar)
file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
stream_handler = logging.StreamHandler()

# Formato mejorado: [2024-03-14 10:00:00] [INFO   ] Mensaje
formatter = logging.Formatter(
    fmt="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

_log.addHandler(file_handler)
_log.addHandler(stream_handler)

_log.info("--- Claude Usage Indicator Started ---")
