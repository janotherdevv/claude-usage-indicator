from .config import ASSETS_DIR, get_theme

# Obsidian Palette: colores fijos para fondos y texto; los arcos usan utilization_color()
_PALETTE_OBSIDIAN = {
    "bg": (0.035, 0.035, 0.043),        # #09090B Zinc 950
    "zinc_100": (0.957, 0.957, 0.961),  # #F4F4F5
    "zinc_400": (0.631, 0.631, 0.702),  # #A1A1AA
    "zinc_500": (0.443, 0.443, 0.482),  # #71717A
}

# Stops para color progresivo: 0%=verde → 60%=ámbar → 85%=rojo → 100%=morado
_COLOR_STOPS = [
    (0,   60,  (0.086, 0.639, 0.290), (0.851, 0.467, 0.024)),  # #16A34A → #D97706
    (60,  85,  (0.851, 0.467, 0.024), (0.863, 0.149, 0.149)),  # #D97706 → #DC2626
    (85, 100,  (0.863, 0.149, 0.149), (0.576, 0.200, 0.918)),  # #DC2626 → #9333EA
]


def utilization_color(utilization):
    """Devuelve RGB interpolado: verde(0%) → ámbar(60%) → rojo(85%) → morado(100%)."""
    u = max(0.0, min(100.0, float(utilization)))
    for lo, hi, c0, c1 in _COLOR_STOPS:
        if u <= hi:
            t = (u - lo) / (hi - lo) if hi > lo else 1.0
            return tuple(c0[i] + t * (c1[i] - c0[i]) for i in range(3))
    return (0.576, 0.200, 0.918)  # morado fijo para >100%

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
    """0=normal(<60%) · 1=warning(60-85%) · 2=critical(85-95%) · 3=extreme(≥95%)."""
    if utilization >= 95:
        return 3
    if utilization >= 85:
        return 2
    if utilization >= 60:
        return 1
    return 0


def get_menu_css():
    """Returns CSS to force a dark theme for the tray context menu."""
    # Zinc 950 (#09090B) for background, Zinc 100 (#F4F4F5) for text
    css = """
        menu, .menu, menuitem {
            background-color: #09090B;
            color: #F4F4F5;
            border: 1px solid #27272A;
        }
        menuitem:hover {
            background-color: #18181B;
            color: #FFFFFF;
        }
        menu separator {
            background-color: #27272A;
            margin: 4px 0;
        }
        /* Suppress arrows in submenus */
        menu { -GtkMenu-double-arrows: 0; }
        menu > arrow { min-height: 0; min-width: 0; opacity: 0; }
    """
    return css.encode()

def get_palette():
    if get_theme() == "classic":
        return _PALETTE_CLASSIC
    return _PALETTE_OBSIDIAN


def classic_tier_color(utilization):
    """Color RGB del arco clásico — usa la misma interpolación progresiva que Obsidian."""
    return utilization_color(utilization)


def get_classic_bar_css(utilization):
    r, g, b = utilization_color(utilization)
    color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
    css = (
        f"progressbar > trough > progress {{ background-color: {color};"
        " background-image: none; border-radius: 4px; }"
    )
    return css.encode()


def icon_path_for(utilization):
    return str(ASSETS_DIR / _ICON_NAMES[min(tier(utilization), 2)])


def icon_names():
    return _ICON_NAMES
