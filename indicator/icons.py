import io
import math
import cairo

from .theme import arc_color, get_palette


def draw_gauge(ctx, x, y, size, five_h_util, seven_d_util, is_tray=False):
    """
    Dibuja el 'Obsidian Gauge' con dos anillos concéntricos.
    - Anillo Exterior (7d): Fino, órbita sutil.
    - Anillo Interior (5h): Más grueso, pulso inmediato.
    """
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    palette = get_palette()

    # Parámetros según escala
    # Tray icon es ~22px, Ventana es ~200px
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

    start_angle = -math.pi / 2  # 12 en punto
    full_sweep = 2 * math.pi

    # --- Anillo Exterior (7-Day) ---
    ctx.set_line_width(outer_stroke)
    # Track
    ctx.set_source_rgba(1, 1, 1, 0.08)
    ctx.arc(x, y, outer_radius, 0, full_sweep)
    ctx.stroke()

    # Progress
    fraction_7d = min(seven_d_util / 100.0, 1.0)
    if fraction_7d > 0:
        r, g, b = arc_color(seven_d_util)
        ctx.set_source_rgb(r, g, b)
        ctx.arc(x, y, outer_radius, start_angle, start_angle + full_sweep * fraction_7d)
        ctx.stroke()

    # --- Anillo Interior (5-Hour) ---
    ctx.set_line_width(inner_stroke)
    # Track
    ctx.set_source_rgba(1, 1, 1, 0.12)
    ctx.arc(x, y, inner_radius, 0, full_sweep)
    ctx.stroke()

    # Progress
    fraction_5h = min(five_h_util / 100.0, 1.0)
    if fraction_5h > 0:
        r, g, b = arc_color(five_h_util)
        ctx.set_source_rgb(r, g, b)
        ctx.arc(x, y, inner_radius, start_angle, start_angle + full_sweep * fraction_5h)
        ctx.stroke()


def render_icon(five_h_util, seven_d_util, size=22):
    """Renderiza el icono para el tray."""
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
    """Genera iconos iniciales (opcional, para retrocompatibilidad)."""
    # Usamos 0% por defecto para el primer arranque
    write_dynamic_icon(0, 0)
