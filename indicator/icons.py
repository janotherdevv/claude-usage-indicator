import io
import math

import cairo

from .config import ASSETS_DIR
from .theme import arc_color, icon_names


def _render_arc_icon(utilization, size=22):
    """Renderiza un icono cuadrado con arco de progreso de 270°.
    Devuelve bytes PNG.
    """
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surface)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)

    cx, cy = size / 2, size / 2
    radius = size * 0.36       # ~8px en 22px
    stroke = size * 0.114      # ~2.5px en 22px
    start_angle = math.pi * 0.75   # 135° — esquina inferior izquierda
    sweep = math.pi * 1.5          # 270°

    ctx.set_line_width(stroke)

    # Track: blanco al 20% de opacidad
    ctx.set_source_rgba(1, 1, 1, 0.20)
    ctx.arc(cx, cy, radius, start_angle, start_angle + sweep)
    ctx.stroke()

    # Fill: color proporcional a la utilización
    fraction = min(utilization / 100.0, 1.0)
    if fraction > 0:
        r, g, b = arc_color(utilization)
        ctx.set_source_rgb(r, g, b)
        ctx.arc(cx, cy, radius, start_angle, start_angle + sweep * fraction)
        ctx.stroke()

    buf = io.BytesIO()
    surface.write_to_png(buf)
    return buf.getvalue()


def generate_icons():
    """Genera los tres iconos de arco representativos."""
    ASSETS_DIR.mkdir(exist_ok=True)
    states = [45, 80, 95]  # OK / WARN / CRIT
    for name, util in zip(icon_names(), states):
        (ASSETS_DIR / name).write_bytes(_render_arc_icon(util))
