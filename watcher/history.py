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

def get_weekly_history():
    """
    Extrae los picos de uso diario directamente del archivo de logs,
    respetando el ciclo semanal actual.
    """
    if not LOG_PATH.exists():
        return []

    # Patrones para buscar en el log
    pattern_usage = re.compile(r"\[(\d{4}-\d{2}-\d{2}).*?7d window: (\d+\.\d+)%")
    pattern_reset = re.compile(r"Reset.*?detectado.*?Reset: ([\d\-\:T\+\.]+)")
    
    history = {}
    last_cycle_reset = ""

    try:
        with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                # 1. Detectar si hubo un reset de ciclo en el pasado
                reset_match = pattern_reset.search(line)
                if reset_match:
                    new_reset = reset_match.group(1)
                    # Si detectamos un reset nuevo en el log, vaciamos lo anterior
                    if new_reset != last_cycle_reset:
                        history = {}
                        last_cycle_reset = new_reset
                
                # 2. Extraer datos de uso
                usage_match = pattern_usage.search(line)
                if usage_match:
                    date_str, val_str = usage_match.groups()
                    val = float(val_str)
                    # Guardamos el valor máximo para cada fecha
                    if date_str not in history or val > history[date_str]:
                        history[date_str] = val
                        
    except Exception as e:
        _log.error(f"Error reading logs for history: {e}")
        return []

    # 3. Filtrar por los últimos 7 días y formatear para el gauge
    results = []
    now = datetime.now()
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        date_str = day.strftime("%Y-%m-%d")
        if date_str in history:
            results.append((day.weekday(), history[date_str]))
            
    return results
