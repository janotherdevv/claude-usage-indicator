from .config import ASSETS_DIR

# Colors in (R, G, B) normalized for Cairo (0.0 to 1.0)
# Obsidian Palette: High-precision, monochromatic Indigo-Blue tones
_PALETTE = {
    "bg": (0.035, 0.035, 0.043),      # #09090B Zinc 950
    "accent": (0.388, 0.400, 0.945),  # #6366F1 Indigo 500 (Primary)
    "accent_dim": (0.506, 0.549, 0.973), # #818CF8 Indigo 400 (Secondary)
    "zinc_100": (0.957, 0.957, 0.961), # #F4F4F5
    "zinc_400": (0.631, 0.631, 0.702), # #A1A1AA
    "zinc_500": (0.443, 0.443, 0.482), # #71717A
}

_ICON_NAMES = ["icon_ok.png", "icon_warn.png", "icon_crit.png"]


def tier(utilization):
    """Thresholds for intensity and pulse behavior."""
    if utilization >= 90:
        return 2
    if utilization >= 70:
        return 1
    return 0


def get_palette():
    return _PALETTE


def icon_path_for(utilization):
    return str(ASSETS_DIR / _ICON_NAMES[tier(utilization)])


def icon_names():
    return _ICON_NAMES
