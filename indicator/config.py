import logging
import logging.handlers
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

# El archivo activo será indicator.log
LOG_PATH = LOG_DIR / "indicator.log"

_log = logging.getLogger("claude_usage")
_log.setLevel(logging.INFO)

# Handler que rota a medianoche
file_handler = logging.handlers.TimedRotatingFileHandler(
    LOG_PATH, when="midnight", interval=1, backupCount=30, encoding="utf-8"
)

# Función para que al rotar el nombre sea exactamente la fecha: YYYY-MM-DD.log
def daily_namer(default_name):
    # default_name suele ser indicator.log.YYYY-MM-DD
    parts = default_name.split('.')
    if len(parts) >= 3:
        # Extraemos la fecha (última parte) y le ponemos .log
        return str(LOG_DIR / f"{parts[-1]}.log")
    return default_name

file_handler.namer = daily_namer
stream_handler = logging.StreamHandler()

# Formato mejorado: [2024-03-14 10:00:00] [INFO   ] Mensaje
formatter = logging.Formatter(
    fmt="[%(asctime)s] [%(levelname)-8s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

_log.addHandler(file_handler)
_log.addHandler(stream_handler)

_log.info("--- Claude Usage Indicator Started ---")
