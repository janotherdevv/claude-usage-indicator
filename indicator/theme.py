from .config import ASSETS_DIR

# Las tres listas están indexadas por nivel (0/1/2), así que añadir un nuevo
# nivel solo requiere actualizar tier() y añadir una entrada a cada lista.
_ARC_COLORS = [
    (0.149, 0.635, 0.412),  # #26A269 verde
    (0.898, 0.647, 0.039),  # #E5A50A ámbar
    (0.753, 0.110, 0.157),  # #C01C28 rojo
]
_BAR_CSS = [
    b"progressbar > trough > progress { background-color: #26A269; background-image: none; }",
    b"progressbar > trough > progress { background-color: #E5A50A; background-image: none; }",
    b"progressbar > trough > progress { background-color: #C01C28; background-image: none; }",
]
_ICON_NAMES = ["icon_ok.png", "icon_warn.png", "icon_crit.png"]


def tier(utilization):
    """Fuente única de verdad para umbrales. Devuelve 0=verde, 1=ámbar, 2=rojo."""
    if utilization >= 90:
        return 2
    if utilization >= 70:
        return 1
    return 0


def arc_color(utilization):
    return _ARC_COLORS[tier(utilization)]


def bar_css(utilization):
    return _BAR_CSS[tier(utilization)]


def icon_path_for(utilization):
    return str(ASSETS_DIR / _ICON_NAMES[tier(utilization)])


def icon_names():
    return _ICON_NAMES
