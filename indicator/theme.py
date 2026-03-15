from .config import ASSETS_DIR, get_settings

# Obsidian Palette: High-precision, monochromatic Indigo-Blue tones
_PALETTE_OBSIDIAN = {
    "bg": (0.035, 0.035, 0.043),      # #09090B Zinc 950
    "accent": (0.388, 0.400, 0.945),  # #6366F1 Indigo 500 (Primary)
    "accent_dim": (0.506, 0.549, 0.973), # #818CF8 Indigo 400 (Secondary)
    "zinc_100": (0.957, 0.957, 0.961), # #F4F4F5
    "zinc_400": (0.631, 0.631, 0.702), # #A1A1AA
    "zinc_500": (0.443, 0.443, 0.482), # #71717A
}

# Classic Palette (from main branch)
_PALETTE_CLASSIC = [
    (0.149, 0.635, 0.412),  # #26A269 verde
    (0.898, 0.647, 0.039),  # #E5A50A ámbar
    (0.753, 0.110, 0.157),  # #C01C28 rojo
]

_BAR_CSS_CLASSIC = [
    b"progressbar > trough > progress { background-color: #26A269; background-image: none; border-radius: 4px; }",
    b"progressbar > trough > progress { background-color: #E5A50A; background-image: none; border-radius: 4px; }",
    b"progressbar > trough > progress { background-color: #C01C28; background-image: none; border-radius: 4px; }",
]

_ICON_NAMES = ["icon_ok.png", "icon_warn.png", "icon_crit.png"]


def tier(utilization):
    """Thresholds for intensity and pulse behavior."""
    if utilization >= 90:
        return 2
    if utilization >= 70:
        return 1
    return 0


def get_palette():
    theme = get_settings().get("theme", "obsidian")
    if theme == "classic":
        return _PALETTE_CLASSIC
    return _PALETTE_OBSIDIAN


def get_classic_bar_css(utilization):
    return _BAR_CSS_CLASSIC[tier(utilization)]


def icon_path_for(utilization):
    return str(ASSETS_DIR / _ICON_NAMES[tier(utilization)])


def icon_names():
    return _ICON_NAMES
