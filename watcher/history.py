import logging
import re
from datetime import datetime, timedelta
from .config import LOG_PATH

_log = logging.getLogger("claude_usage")

def update_daily_usage(value, resets_at=""):
    """
    Ahora es un no-op informativo.
    La persistencia ocurre automáticamente mediante el log que genera api.py.
    """
    pass

def _log_files_for_last_n_days(n):
    """Devuelve los ficheros de log relevantes para los últimos n días (más reciente primero)."""
    log_dir = LOG_PATH.parent
    files = []
    now = datetime.now()
    for i in range(n - 1, -1, -1):
        day = now - timedelta(days=i)
        if i == 0:
            # El fichero activo del día actual
            if LOG_PATH.exists():
                files.append(LOG_PATH)
        else:
            # Ficheros archivados: YYYY-MM-DD.log
            archived = log_dir / f"{day.strftime('%Y-%m-%d')}.log"
            if archived.exists():
                files.append(archived)
    return files

def _current_cycle_reset(pattern, log_files):
    """Devuelve la fecha de reset del ciclo 7d activo (la última vista en los logs)."""
    current = None
    for log_file in log_files:
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    m = pattern.search(line)
                    if m:
                        current = m.group(3).split(",")[0]
        except Exception:
            pass
    return current


def get_last_known_usage():
    """Busca la última entrada de uso en el log activo para restaurar el estado tras un reinicio."""
    if not LOG_PATH.exists():
        return None
    
    pattern_usage = re.compile(
        r"5h window: (\d+\.\d+)% \(resets: ([^)]+)\) \| 7d window: (\d+\.\d+)% \(resets: ([^)]+)\)"
    )
    
    last_data = None
    try:
        # Leemos el final del fichero (últimas 20 líneas aprox) para eficiencia
        with open(LOG_PATH, "rb") as f:
            f.seek(0, 2)
            filesize = f.tell()
            f.seek(max(0, filesize - 2000))
            lines = f.read().decode(errors="replace").splitlines()
            
            for line in reversed(lines):
                m = pattern_usage.search(line)
                if m:
                    u5h, r5h, u7d, r7d = m.groups()
                    last_data = {
                        "five_hour": {"utilization": float(u5h), "resets_at": r5h},
                        "seven_day": {"utilization": float(u7d), "resets_at": r7d}
                    }
                    break
    except Exception:
        pass
    return last_data


def get_weekly_history():
    """
    Extrae los picos de uso diario directamente del archivo de logs,
    respetando el ciclo semanal actual. Lee tanto el log activo como
    los ficheros archivados de los últimos 7 días.

    Determina primero cuál es el ciclo 7d activo y solo acumula
    entradas que pertenecen a ese ciclo, ignorando datos de ciclos anteriores.
    """
    pattern_usage = re.compile(
        r"\[(\d{4}-\d{2}-\d{2}).*?7d window: (\d+\.\d+)% \(resets: ([^)]+)\)"
    )

    log_files = _log_files_for_last_n_days(7)
    active_reset = _current_cycle_reset(pattern_usage, log_files)
    if active_reset is None:
        return []

    history = {}

    for log_file in log_files:
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    m = pattern_usage.search(line)
                    if not m:
                        continue
                    date_str, val_str, resets_str = m.groups()
                    # Solo acumular entradas del ciclo activo
                    if resets_str.split(",")[0] != active_reset:
                        continue
                    val = float(val_str)
                    if date_str not in history or val > history[date_str]:
                        history[date_str] = val
        except Exception as e:
            _log.error(f"Error reading log {log_file}: {e}")

    # 3. Filtrar por los últimos 7 días y formatear para el gauge
    results = []
    now = datetime.now()
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        date_str = day.strftime("%Y-%m-%d")
        if date_str in history:
            results.append((day.weekday(), history[date_str]))
            
    return results
