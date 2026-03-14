from .config import ASSETS_DIR

# Colors in (R, G, B) normalized for Cairo (0.0 to 1.0)
# Obsidian Palette: Deep, "etched" instrument feel
_PALETTE = {
    "bg": (0.039, 0.039, 0.047),      # #0A0A0C Deep Obsidian
    "safe": (0.0, 0.949, 0.651),    # #00F2A6 Mint Aura
    "warn": (1.0, 0.722, 0.0),      # #FFB800 Solar Amber
    "crit": (1.0, 0.231, 0.231),    # #FF3B3B Crimson Pulse
    "dim": (0.91, 0.886, 0.957, 0.4), # Translucent Lavender-tinted text
}

_ARC_COLORS = [
    _PALETTE["safe"],
    _PALETTE["warn"],
    _PALETTE["crit"],
]

_ICON_NAMES = ["icon_ok.png", "icon_warn.png", "icon_crit.png"]


def tier(utilization):
    """Source of truth for usage thresholds."""
    if utilization >= 90:
        return 2
    if utilization >= 70:
        return 1
    return 0


def arc_color(utilization):
    return _ARC_COLORS[tier(utilization)]


def get_palette():
    return _PALETTE


def icon_path_for(utilization):
    return str(ASSETS_DIR / _ICON_NAMES[tier(utilization)])


def icon_names():
    return _ICON_NAMES
