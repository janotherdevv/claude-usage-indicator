import io
import math
import cairo
from gi.repository import GdkPixbuf, Gdk

from .theme import get_palette, tier, utilization_color
from .config import get_settings


def render_pixbuf(five_h_util, seven_d_util, size=22):
    """Renderiza el icono y lo devuelve como GdkPixbuf directamente desde memoria."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surface)
    
    draw_gauge(ctx, size/2, size/2, size, five_h_util, seven_d_util, is_tray=True)
    
    # Convertir superficie de Cairo a GdkPixbuf
    pixbuf = Gdk.pixbuf_get_from_surface(surface, 0, 0, size, size)
    return pixbuf


def draw_gauge(ctx, x, y, size, five_h_util, seven_d_util, is_tray=False):
    theme = get_settings().get("theme", "obsidian")
    if theme == "classic":
        draw_classic_gauge(ctx, x, y, size, max(five_h_util, seven_d_util))
    else:
        draw_obsidian_gauge(ctx, x, y, size, five_h_util, seven_d_util, is_tray)


def draw_obsidian_gauge(ctx, x, y, size, five_h_util, seven_d_util, is_tray=False):
    """
    Dibuja el 'Obsidian Gauge' con dos anillos concéntricos.
    - Anillo Exterior (7d): Fino, órbita sutil.
    - Anillo Interior (5h): Más grueso, pulso inmediato.
    """
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)

    # Parámetros según escala
    if is_tray:
        outer_radius = size * 0.40
        inner_radius = size * 0.22
        outer_stroke = size * 0.08
        inner_stroke = size * 0.14
    else:
        outer_radius = size * 0.38
        inner_radius = size * 0.28
        outer_stroke = size * 0.04
        inner_stroke = size * 0.08

    start_angle = -math.pi / 2
    full_sweep = 2 * math.pi

    # --- Anillo Exterior (7-Day) ---
    ctx.set_line_width(outer_stroke)
    # Track: Muted Zinc path
    ctx.set_source_rgba(0.4, 0.4, 0.4, 0.12)
    ctx.arc(x, y, outer_radius, 0, full_sweep)
    ctx.stroke()

    # Progress: color progresivo según utilización del período 7d
    fraction_7d = min(seven_d_util / 100.0, 1.0)
    if fraction_7d > 0:
        r, g, b = utilization_color(seven_d_util)
        ctx.set_source_rgb(r, g, b)
        ctx.arc(x, y, outer_radius, start_angle, start_angle + full_sweep * fraction_7d)
        ctx.stroke()

    # --- Anillo Interior (5-Hour) ---
    ctx.set_line_width(inner_stroke)
    # Track: Slightly more visible Zinc path
    ctx.set_source_rgba(0.4, 0.4, 0.4, 0.18)
    ctx.arc(x, y, inner_radius, 0, full_sweep)
    ctx.stroke()

    # Progress: color progresivo según utilización del período 5h
    fraction_5h = min(five_h_util / 100.0, 1.0)
    if fraction_5h > 0:
        r, g, b = utilization_color(five_h_util)
        ctx.set_source_rgb(r, g, b)
        ctx.arc(x, y, inner_radius, start_angle, start_angle + full_sweep * fraction_5h)
        ctx.stroke()


def draw_classic_gauge(ctx, cx, cy, size, utilization):
    """Renderiza un icono cuadrado con arco de progreso de 270° (Estilo Clásico)."""
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    palette = get_palette()

    radius = size * 0.36
    stroke = size * 0.114
    start_angle = math.pi * 0.75   # 135°
    sweep = math.pi * 1.5          # 270°

    ctx.set_line_width(stroke)

    # Track: blanco al 20% de opacidad
    ctx.set_source_rgba(1, 1, 1, 0.20)
    ctx.arc(cx, cy, radius, start_angle, start_angle + sweep)
    ctx.stroke()

    # Fill: color proporcional a la utilización
    fraction = min(utilization / 100.0, 1.0)
    if fraction > 0:
        r, g, b = palette[tier(utilization)]
        ctx.set_source_rgb(r, g, b)
        ctx.arc(cx, cy, radius, start_angle, start_angle + sweep * fraction)
        ctx.stroke()


def render_icon(five_h_util, seven_d_util, size=22):
    """Renderiza el icono para el tray (PNG bytes)."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surface)
    draw_gauge(ctx, size/2, size/2, size, five_h_util, seven_d_util, is_tray=True)
    buf = io.BytesIO()
    surface.write_to_png(buf)
    return buf.getvalue()


def write_dynamic_icon(five_h_util, seven_d_util):
    """Escribe el icono actual en assets/icon_current.png."""
    from .config import ASSETS_DIR
    ASSETS_DIR.mkdir(exist_ok=True)
    path = ASSETS_DIR / "icon_current.png"
    path.write_bytes(render_icon(five_h_util, seven_d_util))
    return str(path)


def generate_icons():
    """Genera icono inicial."""
    write_dynamic_icon(0, 0)
