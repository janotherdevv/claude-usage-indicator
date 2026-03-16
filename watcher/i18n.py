from .config import get_language, get_style

_STRINGS_EN = {
    # Menu
    "menu.refresh":     "Refresh Now",
    "menu.design":      "Design",
    "menu.obsidian":    "Obsidian (Concentric)",
    "menu.classic":     "Classic (Arc)",
    "menu.desktop":     "Desktop",
    "menu.language":    "Language",
    "menu.english":     "English",
    "menu.spanish":     "Español",
    "menu.style":       "Style",
    "menu.serious":     "Serious",
    "menu.funny":       "Funny",
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
    # Popup labels (Obsidian + Desktop)
    "label.daily":          "DAILY",
    "label.weekly":         "WEEKLY",
    "label.resets":         "RESETS {time}",
    "label.gauge_loading":  "Usage gauge: loading\u2026",
    "label.gauge_tooltip":  "Daily (5h): {five_h:.0f}%  \u00b7  Weekly (7d): {seven_d:.0f}%",
    "label.stale":          "(stale data)",
    # Classic-specific labels
    "classic.fetching":     "Fetching...",
    "classic.resets":       "resets {time}",
    # Shared status strings (Classic + Desktop + any future theme)
    "shared.conn_error":    "Connection error",
    "shared.updated_now":   "Updated just now",
    "shared.updated_at":    "Updated {time}",
    "shared.stale_suffix":  "(stale)",
    # Notifications
    "notif.normal":   "Back to normal \u2014 {pct}%",
    "notif.warning":  "High usage \u2014 {pct}%  \u00b7  resets {reset}",
    "notif.critical": "Critical usage \u2014 {pct}%!  \u00b7  resets {reset}",
    "notif.extreme":  "EXTREME usage \u2014 {pct}%!!  \u00b7  resets {reset}",
    "notif.limit":    "LIMIT REACHED \u2014 {pct}%!  \u00b7  resets {reset}",
    # Day names
    "day.0": "M",
    "day.1": "T",
    "day.2": "W",
    "day.3": "T",
    "day.4": "F",
    "day.5": "S",
    "day.6": "S",
}

_STRINGS_EN_FUNNY = {
    **_STRINGS_EN,
    "status.safe_label":    "CHILLIN'",
    "status.safe_desc":     "Claude is bored, ask something!",
    "status.warning_label": "HOT STUFF",
    "status.warning_desc":  "Maybe start wrapping up...",
    "status.critical_label":"PANIC MODE",
    "status.critical_desc": "The tokens are screaming",
    "status.extreme_label": "MELTDOWN",
    "status.extreme_desc":  "Start parking Opus, mate...",
    "status.limit_label":   "RIP TOKENS",
    "status.limit_desc":    "Go outside and touch some grass",
    "notif.normal":   "Phew! We're back \u2014 {pct}%",
    "notif.warning":  "Whoa there! {pct}% usage \u2014 reset at {reset}",
    "notif.critical": "PANIC! {pct}% used! \u2014 reset: {reset}",
    "notif.extreme":  "BYE BYE OPUS! {pct}%!! \u2014 reset: {reset}",
    "notif.limit":    "LIMIT REACHED! {pct}%!! \u2014 reset: {reset}",
}

_STRINGS_ES = {
    # Menu
    "menu.refresh":     "Actualizar",
    "menu.design":      "Dise\u00f1o",
    "menu.obsidian":    "Obsidian (Conc\u00e9ntrico)",
    "menu.classic":     "Cl\u00e1sico (Arco)",
    "menu.desktop":     "Escritorio",
    "menu.language":    "Idioma",
    "menu.english":     "English",
    "menu.spanish":     "Espa\u00f1ol",
    "menu.style":       "Estilo",
    "menu.serious":     "Serio",
    "menu.funny":       "Gracioso",
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
    "status.limit_label":   "L\u00CDMITE ALCANZADO",
    "status.limit_desc":    "Tokens completamente agotados",
    # Popup labels (Obsidian + Desktop)
    "label.daily":          "DIARIO",
    "label.weekly":         "SEMANAL",
    "label.resets":         "REINICIA {time}",
    "label.gauge_loading":  "Medidor de uso: cargando\u2026",
    "label.gauge_tooltip":  "Diario (5h): {five_h:.0f}%  \u00b7  Semanal (7d): {seven_d:.0f}%",
    "label.stale":          "(datos desactualizados)",
    # Classic-specific labels
    "classic.fetching":     "Cargando...",
    "classic.resets":       "reinicia {time}",
    # Shared status strings (Classic + Desktop + any future theme)
    "shared.conn_error":    "Error de conexi\u00f3n",
    "shared.updated_now":   "Actualizado ahora mismo",
    "shared.updated_at":    "Actualizado {time}",
    "shared.stale_suffix":  "(desact.)",
    # Notifications
    "notif.normal":   "Volvi\u00f3 a la normalidad \u2014 {pct}%",
    "notif.warning":  "Uso alto \u2014 {pct}%  \u00b7  reinicia {reset}",
    "notif.critical": "Uso cr\u00edtico \u2014 {pct}%!  \u00b7  reinicia {reset}",
    "notif.extreme":  "Uso EXTREMO \u2014 {pct}%!!  \u00b7  reinicia {reset}",
    "notif.limit":    "L\u00cdMITE ALCANZADO \u2014 {pct}%!  \u00b7  reinicia {reset}",
    # Day names
    "day.0": "L",
    "day.1": "M",
    "day.2": "X",
    "day.3": "J",
    "day.4": "V",
    "day.5": "S",
    "day.6": "D",
}

_STRINGS_ES_FUNNY = {
    **_STRINGS_ES,
    "status.safe_label":    "RELAX TOTAL",
    "status.safe_desc":     "Claude est\u00e1 de vacaciones, dale ca\u00f1a",
    "status.warning_label": "CUIDADITO",
    "status.warning_desc":  "Ve aparcando a OPUS...",
    "status.critical_label":"P\u00c1NICO",
    "status.critical_desc": "Los tokens est\u00e1n pidiendo clemencia",
    "status.extreme_label": "¡FUEGO!",
    "status.extreme_desc":  "¡Dile adi\u00f3s a tus prompts!",
    "status.limit_label":   "GAME OVER",
    "status.limit_desc":    "Aprovecha para ver la luz del sol",
    "notif.normal":   "¡Uff! Ya podemos respirar \u2014 {pct}%",
    "notif.warning":  "¡Eh! Un {pct}% usado \u2014 reinicia a las {reset}",
    "notif.critical": "¡P\u00c1NICO! {pct}% gastado \u2014 reinicia: {reset}",
    "notif.extreme":  "¡ADI\u00d3S OPUS! {pct}%!! \u2014 reinicia: {reset}",
    "notif.limit":    "¡GAME OVER! {pct}% gastado \u2014 reinicia: {reset}",
}

_DICTS = {
    ("en", "serious"): _STRINGS_EN,
    ("en", "funny"):   _STRINGS_EN_FUNNY,
    ("es", "serious"): _STRINGS_ES,
    ("es", "funny"):   _STRINGS_ES_FUNNY,
}

_MISSING = object()


def t(key, **kwargs):
    """Return the translated string for `key` in the current language and style.

    Falls back to EN/Serious if the key is missing in the active dict.
    Applies .format(**kwargs) if any kwargs are provided.
    """
    lang = get_language()
    style = get_style()
    
    # Try current lang + style
    val = _DICTS.get((lang, style), _STRINGS_EN).get(key, _MISSING)
    
    # Fallback to current lang + serious
    if val is _MISSING and style != "serious":
        val = _DICTS.get((lang, "serious"), _STRINGS_EN).get(key, _MISSING)
    
    # Fallback to EN + serious
    string = _STRINGS_EN.get(key, key) if val is _MISSING else val
    
    if kwargs:
        try:
            string = string.format(**kwargs)
        except KeyError:
            pass
    return string
