from .config import get_language

_STRINGS_EN = {
    # Menu
    "menu.refresh":     "Refresh Now",
    "menu.design":      "Design",
    "menu.obsidian":    "Obsidian (Concentric)",
    "menu.classic":     "Classic (Arc)",
    "menu.language":    "Language",
    "menu.english":     "English",
    "menu.spanish":     "Español",
    "menu.open_claude": "Open claude.ai",
    "menu.quit":        "Quit",
    # Tooltips (tray icon)
    "tooltip.loading":  "Claude — loading...",
    "tooltip.usage":    "Claude Daily:{five_h:.0f}%  Weekly:{seven_d:.0f}%",
    "tooltip.stale":    "Claude (stale) — Daily:{five_h:.0f}%  Weekly:{seven_d:.0f}%",
    # Status labels (popup header)
    "status.initializing":  "INITIALIZING...",
    "status.interrupted":   "CONNECTION INTERRUPTED",
    "status.safe_label":    "SAFE",
    "status.safe_desc":     "All systems operational",
    "status.warning_label": "WARNING",
    "status.warning_desc":  "Approaching limit",
    "status.critical_label":"CRITICAL",
    "status.critical_desc": "Usage capacity critical",
    "status.extreme_label": "EXTREME",
    "status.extreme_desc":  "Limit almost exhausted",
    "status.limit_label":   "LIMIT REACHED",
    "status.limit_desc":    "Tokens fully exhausted",
    # Obsidian popup labels
    "label.daily":          "DAILY",
    "label.weekly":         "WEEKLY",
    "label.resets":         "RESETS {time}",
    "label.gauge_loading":  "Usage gauge: loading\u2026",
    "label.gauge_tooltip":  "Daily (5h): {five_h:.0f}%  \u00b7  Weekly (7d): {seven_d:.0f}%",
    "label.stale":          "(stale data)",
    # Classic popup labels
    "classic.fetching":     "Fetching...",
    "classic.conn_error":   "Connection error",
    "classic.updated_now":  "Updated just now",
    "classic.updated_at":   "Updated {time}",
    "classic.stale_suffix": "(stale)",
    "classic.resets":       "resets {time}",
    # Notifications
    "notif.normal":   "Back to normal \u2014 {pct}%",
    "notif.warning":  "High usage \u2014 {pct}%  \u00b7  resets {reset}",
    "notif.critical": "Critical usage \u2014 {pct}%!  \u00b7  resets {reset}",
    "notif.extreme":  "EXTREME usage \u2014 {pct}%!!  \u00b7  resets {reset}",
}

_STRINGS_ES = {
    # Menu
    "menu.refresh":     "Actualizar",
    "menu.design":      "Dise\u00f1o",
    "menu.obsidian":    "Obsidian (Conc\u00e9ntrico)",
    "menu.classic":     "Cl\u00e1sico (Arco)",
    "menu.language":    "Idioma",
    "menu.english":     "English",
    "menu.spanish":     "Espa\u00f1ol",
    "menu.open_claude": "Abrir claude.ai",
    "menu.quit":        "Salir",
    # Tooltips
    "tooltip.loading":  "Claude \u2014 cargando...",
    "tooltip.usage":    "Claude Diario:{five_h:.0f}%  Semanal:{seven_d:.0f}%",
    "tooltip.stale":    "Claude (desact.) \u2014 Diario:{five_h:.0f}%  Semanal:{seven_d:.0f}%",
    # Status labels
    "status.initializing":  "INICIANDO...",
    "status.interrupted":   "CONEXI\u00d3N INTERRUMPIDA",
    "status.safe_label":    "SEGURO",
    "status.safe_desc":     "Todo en orden",
    "status.warning_label": "AVISO",
    "status.warning_desc":  "Acerc\u00e1ndose al l\u00edmite",
    "status.critical_label":"CR\u00cdTICO",
    "status.critical_desc": "Capacidad de uso cr\u00edtica",
    "status.extreme_label": "EXTREMO",
    "status.extreme_desc":  "L\u00edmite casi agotado",
    "status.limit_label":   "L\u00cdMITE ALCANZADO",
    "status.limit_desc":    "Tokens completamente agotados",
    # Obsidian popup labels
    "label.daily":          "DIARIO",
    "label.weekly":         "SEMANAL",
    "label.resets":         "REINICIA {time}",
    "label.gauge_loading":  "Medidor de uso: cargando\u2026",
    "label.gauge_tooltip":  "Diario (5h): {five_h:.0f}%  \u00b7  Semanal (7d): {seven_d:.0f}%",
    "label.stale":          "(datos desactualizados)",
    # Classic popup labels
    "classic.fetching":     "Cargando...",
    "classic.conn_error":   "Error de conexi\u00f3n",
    "classic.updated_now":  "Actualizado ahora mismo",
    "classic.updated_at":   "Actualizado {time}",
    "classic.stale_suffix": "(desact.)",
    "classic.resets":       "reinicia {time}",
    # Notifications
    "notif.normal":   "Volvi\u00f3 a la normalidad \u2014 {pct}%",
    "notif.warning":  "Uso alto \u2014 {pct}%  \u00b7  reinicia {reset}",
    "notif.critical": "Uso cr\u00edtico \u2014 {pct}%!  \u00b7  reinicia {reset}",
    "notif.extreme":  "Uso EXTREMO \u2014 {pct}%!!  \u00b7  reinicia {reset}",
}

_DICTS = {"en": _STRINGS_EN, "es": _STRINGS_ES}

_MISSING = object()


def t(key, **kwargs):
    """Return the translated string for `key` in the current language.

    Falls back to EN if the key is missing in the active language dict.
    Applies .format(**kwargs) if any kwargs are provided.
    """
    lang = get_language()
    val = _DICTS.get(lang, _STRINGS_EN).get(key, _MISSING)
    string = _STRINGS_EN.get(key, key) if val is _MISSING else val
    if kwargs:
        string = string.format(**kwargs)
    return string
