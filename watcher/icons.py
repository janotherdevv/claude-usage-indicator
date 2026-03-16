import io
import math
import cairo
from gi.repository import GdkPixbuf, Gdk

from .theme import tier, utilization_color, classic_tier_color
from .config import get_theme
from .i18n import t


def render_pixbuf(five_h_util, seven_d_util, size=22, history=None):
    """Renderiza el icono y lo devuelve como GdkPixbuf directamente desde memoria."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surface)
    
    draw_gauge(ctx, size/2, size/2, size, five_h_util, seven_d_util, is_tray=True, history=history)
    
    # Convertir superficie de Cairo a GdkPixbuf
    pixbuf = Gdk.pixbuf_get_from_surface(surface, 0, 0, size, size)
    return pixbuf


def draw_gauge(ctx, x, y, size, five_h_util, seven_d_util, is_tray=False, history=None):
    if get_theme() == "classic":
        draw_classic_gauge(ctx, x, y, size, max(five_h_util, seven_d_util))
    else:
        draw_obsidian_gauge(ctx, x, y, size, five_h_util, seven_d_util, is_tray, history=history)


def draw_obsidian_gauge(ctx, x, y, size, five_h_util, seven_d_util, is_tray=False, history=None):
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
    ctx.new_path()
    ctx.set_line_width(outer_stroke)
    # Track: Muted Zinc path
    ctx.set_source_rgba(0.4, 0.4, 0.4, 0.12)
    ctx.arc(x, y, outer_radius, 0, full_sweep)
    ctx.stroke()

    # Progress: color progresivo según utilización del período 7d
    fraction_7d = min(seven_d_util / 100.0, 1.0)
    if fraction_7d > 0:
        ctx.new_path()
        r, g, b = utilization_color(seven_d_util)
        ctx.set_source_rgb(r, g, b)
        ctx.arc(x, y, outer_radius, start_angle, start_angle + full_sweep * fraction_7d)
        ctx.stroke()

    # --- Daily History Markers (Arrows + Letters) ---
    if history and not is_tray:
        # Solo dibujamos marcadores en la ventana popup
        for weekday, value in history:
            if value <= 0: continue
            
            ctx.save() # Aislar estilo para marcadores
            ctx.new_path()
            angle = start_angle + full_sweep * min(value / 100.0, 1.0)
            
            mr, mg, mb = utilization_color(value)
            
            # Posición base en el arco
            ax = x + outer_radius * math.cos(angle)
            ay = y + outer_radius * math.sin(angle)
            
            # 1. Agujero de fondo (para "cortar" la barra)
            ctx.new_path()
            ctx.arc(ax, ay, size * 0.022, 0, 2 * math.pi)
            ctx.set_source_rgb(0.035, 0.035, 0.043) # Obsidian bg
            ctx.fill()
            
            # 2. Nodo / cuenta de historial (minimalista y brillante)
            ctx.new_path()
            ctx.arc(ax, ay, size * 0.010, 0, 2 * math.pi)
            ctx.set_source_rgba(mr, mg, mb, 1.0)
            ctx.fill()
            
            # 3. Línea conector sutil
            dist_base = outer_radius + (size * 0.030)
            line_end = outer_radius + (size * 0.055)
            
            ctx.new_path()
            ctx.set_line_width(size * 0.003)
            ctx.set_source_rgba(mr, mg, mb, 0.4)
            ctx.move_to(x + dist_base * math.cos(angle), y + dist_base * math.sin(angle))
            ctx.line_to(x + line_end * math.cos(angle), y + line_end * math.sin(angle))
            ctx.stroke()
            
            # 4. Dibujar letra flotante con estilo depurado
            day_letter = t(f"day.{weekday}")
            ctx.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            ctx.set_font_size(size * 0.035)
            
            dist_text = line_end + (size * 0.025)
            tx = x + dist_text * math.cos(angle)
            ty = y + dist_text * math.sin(angle)
            
            extents = ctx.text_extents(day_letter)
            ctx.set_source_rgba(mr, mg, mb, 0.95)
            ctx.move_to(tx - extents.width/2 - extents.x_bearing, ty + extents.height/2)
            ctx.show_text(day_letter)
            ctx.restore()
        
        ctx.new_path()

    # --- Anillo Interior (5-Hour) ---
    ctx.new_path()
    ctx.set_line_width(inner_stroke)
    # Track: Slightly more visible Zinc path
    ctx.set_source_rgba(0.4, 0.4, 0.4, 0.18)
    ctx.arc(x, y, inner_radius, 0, full_sweep)
    ctx.stroke()

    # Progress: color progresivo según utilización del período 5h
    fraction_5h = min(five_h_util / 100.0, 1.0)
    if fraction_5h > 0:
        ctx.new_path()
        r, g, b = utilization_color(five_h_util)
        
        # Propuesta: Estado Sólido Progresivo (90% -> 100%)
        fill_opacity = 0.0
        if five_h_util > 90:
            fill_opacity = min(1.0, (five_h_util - 90) / 10.0)

        if fill_opacity > 0:
            # Gradiente Radial Progresivo
            pat = cairo.RadialGradient(x, y - inner_radius*0.2, inner_radius*0.1, 
                                       x, y, inner_radius + inner_stroke/2)
            
            pat.add_color_stop_rgba(0, min(1.0, r*1.2), min(1.0, g*1.2), min(1.0, b*1.2), 0.95 * fill_opacity)
            pat.add_color_stop_rgba(1, r, g, b, 0.85 * fill_opacity)
            
            ctx.set_source(pat)
            ctx.arc(x, y, inner_radius + inner_stroke/2, 0, full_sweep)
            ctx.fill()
            
            ctx.set_source_rgba(r, g, b, 1.0 - (fill_opacity * 0.5))
        else:
            ctx.set_source_rgb(r, g, b)

        ctx.arc(x, y, inner_radius, start_angle, start_angle + full_sweep * fraction_5h)
        ctx.stroke()


def draw_classic_gauge(ctx, cx, cy, size, utilization):
    """Renderiza un icono cuadrado con arco de progreso de 270° (Estilo Clásico)."""
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)

    radius = size * 0.36
    stroke = size * 0.114
    start_angle = math.pi * 0.75   # 135°
    sweep = math.pi * 1.5          # 270°

    ctx.set_line_width(stroke)

    # Track: blanco al 20% de opacidad
    ctx.new_path()
    ctx.set_source_rgba(1, 1, 1, 0.20)
    ctx.arc(cx, cy, radius, start_angle, start_angle + sweep)
    ctx.stroke()

    # Fill: color proporcional a la utilización
    fraction = min(utilization / 100.0, 1.0)
    if fraction > 0:
        ctx.new_path()
        r, g, b = classic_tier_color(utilization)
        ctx.set_source_rgb(r, g, b)
        ctx.arc(cx, cy, radius, start_angle, start_angle + sweep * fraction)
        ctx.stroke()


def render_icon(five_h_util, seven_d_util, size=22, history=None):
    """Renderiza el icono para el tray (PNG bytes)."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surface)
    draw_gauge(ctx, size/2, size/2, size, five_h_util, seven_d_util, is_tray=True, history=history)
    buf = io.BytesIO()
    surface.write_to_png(buf)
    return buf.getvalue()


def write_dynamic_icon(five_h_util, seven_d_util, history=None):
    """Escribe el icono actual en assets/icon_current.png."""
    from .config import ASSETS_DIR
    ASSETS_DIR.mkdir(exist_ok=True)
    path = ASSETS_DIR / "icon_current.png"
    path.write_bytes(render_icon(five_h_util, seven_d_util, history=history))
    return str(path)


def generate_icons():
    """Genera icono inicial."""
    write_dynamic_icon(0, 0)
