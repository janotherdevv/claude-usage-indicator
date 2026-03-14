import io
import math

import cairo

from .config import ASSETS_DIR
from .theme import arc_color, icon_names


def _render_wide_bar_icon(utilization, width=44, height=22):
    """Renderiza un icono ancho con una única barra horizontal panorámica.
    Devuelve bytes PNG.
    """
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)

    # Margen de 2px a los lados, barra de 10px de alto centrada verticalmente
    bar_h = 10.0
    x_start = 2
    x_end = width - 2
    y_center = height / 2
    bar_width = x_end - x_start

    ctx.set_line_width(bar_h)

    # Track: Fondo tenue (blanco al 15% opacidad)
    ctx.set_source_rgba(1, 1, 1, 0.15)
    ctx.move_to(x_start + bar_h/2, y_center)
    ctx.line_to(x_end - bar_h/2, y_center)
    ctx.stroke()

    # Fill: Color basado en utilización
    fraction = min(utilization / 100.0, 1.0)
    if fraction > 0:
        r, g, b = arc_color(utilization)
        ctx.set_source_rgb(r, g, b)
        ctx.move_to(x_start + bar_h/2, y_center)
        # El fill crece proporcionalmente dentro del track de 40px
        ctx.line_to(x_start + bar_h/2 + (bar_width - bar_h) * fraction, y_center)
        ctx.stroke()

    buf = io.BytesIO()
    surface.write_to_png(buf)
    return buf.getvalue()


def generate_icons():
    """Genera los tres iconos de barra panorámica representativos.
    """
    ASSETS_DIR.mkdir(exist_ok=True)
    states = [45, 80, 95]  # OK / WARN / CRIT
    for name, util in zip(icon_names(), states):
        (ASSETS_DIR / name).write_bytes(_render_wide_bar_icon(util))
