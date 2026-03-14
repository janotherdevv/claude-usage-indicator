import io
import math

import cairo

from .config import ASSETS_DIR
from .theme import arc_color, icon_names


def _render_arc_icon(utilization, size=22):
    """Renderiza un icono de arco de progreso circular. Devuelve bytes PNG.

    El arco barre 270° en sentido horario desde las 7 en punto (225°) hasta
    las 5 en punto (135°). Un track tenue blanco muestra el rango completo;
    el fill de color cubre la proporción correspondiente al valor de utilización.
    """
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surface)

    cx, cy = size / 2, size / 2
    radius = (size / 2) - 2 - 1.5   # 2px margen + mitad del grosor de línea
    start = math.radians(225)        # 7 en punto
    full_end = math.radians(135)     # 5 en punto (270° en sentido horario)

    ctx.set_line_width(3.0)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)

    # Track base: blanco al 25% de opacidad
    ctx.set_source_rgba(1, 1, 1, 0.25)
    ctx.arc(cx, cy, radius, start, full_end)
    ctx.stroke()

    # Fill de color proporcional a la utilización
    fraction = min(utilization / 100.0, 1.0)
    if fraction > 0:
        r, g, b = arc_color(utilization)
        ctx.set_source_rgb(r, g, b)
        ctx.arc(cx, cy, radius, start, start + fraction * math.radians(270))
        ctx.stroke()

    buf = io.BytesIO()
    surface.write_to_png(buf)
    return buf.getvalue()


def generate_icons():
    """Genera los tres iconos de estado representativos y los guarda en assets/.

    Usa valores fijos representativos (45 / 80 / 95 %) en lugar del porcentaje
    real — Gtk.StatusIcon requiere un archivo estático en disco y no puede
    renderizar surfaces de Cairo directamente. El porcentaje real se muestra
    en el tooltip y en el popup.
    """
    ASSETS_DIR.mkdir(exist_ok=True)
    for name, util in zip(icon_names(), [45, 80, 95]):
        (ASSETS_DIR / name).write_bytes(_render_arc_icon(util))
