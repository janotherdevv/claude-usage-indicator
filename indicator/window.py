import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk

import cairo
import math
from datetime import datetime

from .theme import get_palette, tier
from .api import format_reset_time
from .icons import draw_gauge

def _status_markup(utilization):
    palette = get_palette()
    t = tier(utilization)
    
    # Mapping simple para estados (Norman-approved)
    if t == 0:
        label, desc = "SAFE", "All systems operational"
        color = "#A1A1AA" # Zinc 400
    elif t == 1:
        label, desc = "WARNING", "Approaching limit"
        color = "#818CF8" # Indigo 400
    else:
        label, desc = "CRITICAL", "Usage capacity critical"
        color = "#6366F1" # Indigo 500

    return f'<span foreground="{color}" weight="bold" size="small">{label}</span>\n<span size="medium" foreground="#F4F4F5">{desc}</span>'

# Obsidian Dark: Singular, integrated object
_WINDOW_CSS = b"""
window {
    background-color: #09090B; /* Zinc 950 */
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
}
label {
    color: #F4F4F5; /* Zinc 100 */
    font-family: "Inter", "Cantarell", "Sans";
}
*:focus {
    outline: none;
}
.whisper-label {
    color: #71717A; /* Zinc 500 */
    font-size: 0.75em;
    font-weight: 500;
}
.metric-box {
    padding: 8px 12px;
    border-radius: 10px;
    background-color: rgba(255, 255, 255, 0.03);
    transition: background-color 0.2s ease;
}
.metric-box:hover {
    background-color: rgba(255, 255, 255, 0.06);
}
.metric-label {
    font-size: 0.72em;
    font-weight: 700;
    letter-spacing: 0.08em;
}
.metric-value {
    font-size: 1.2em;
    font-weight: 600;
    color: #FAFAFA;
}
menu {
    background-color: #09090B;
    color: #D4D4D8;
    border: 1px solid rgba(255, 255, 255, 0.1);
}
menuitem label {
    color: #D4D4D8;
}
menuitem:hover {
    background-color: rgba(255, 255, 255, 0.08);
}
"""

_css_provider = None

def _apply_theme(window):
    global _css_provider
    screen = window.get_screen()
    visual = screen.get_rgba_visual()
    if visual:
        window.set_visual(visual)
    
    if _css_provider is not None:
        return
    _css_provider = Gtk.CssProvider()
    _css_provider.load_from_data(_WINDOW_CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        _css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )

def _hex(rgb):
    return f"#{int(rgb[0]*255):02x}{int(rgb[1]*255):02x}{int(rgb[2]*255):02x}"

class UsageWindow:
    def __init__(self):
        self.window = Gtk.Window()
        _apply_theme(self.window)

        self.window.set_skip_taskbar_hint(True)
        self.window.set_skip_pager_hint(True)
        self.window.set_decorated(False)
        self.window.set_border_width(20)
        self.window.set_resizable(False)
        self.window.connect("focus-out-event", lambda w, e: w.hide() or True)
        self.window.connect("delete-event", lambda w, e: w.hide() or True)

        self.five_h_util = 0.0
        self.seven_d_util = 0.0
        self.target_5h = 0.0
        self.target_7d = 0.0
        self.pulse_val = 0.0
        self._pulsing = True

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.window.add(main_box)

        # Status Header
        self._status_label = Gtk.Label()
        self._status_label.set_markup('<span foreground="#71717A" weight="bold">INITIALIZING...</span>')
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.set_line_wrap(True)
        main_box.pack_start(self._status_label, False, False, 0)

        # Gauge Container
        gauge_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.darea = Gtk.DrawingArea()
        self.darea.set_size_request(200, 200)
        self.darea.connect("draw", self._on_draw)
        gauge_box.pack_start(self.darea, True, True, 0)
        main_box.pack_start(gauge_box, True, True, 0)

        # Metrics Column (Legend and Details)
        metrics_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.pack_start(metrics_col, False, False, 0)

        self._m_daily = self._make_metric("DIARIO")
        metrics_col.pack_start(self._m_daily["box"], False, False, 0)

        self._m_weekly = self._make_metric("SEMANAL")
        metrics_col.pack_start(self._m_weekly["box"], False, False, 0)

        GLib.timeout_add(32, self._tick)

    def _make_metric(self, label_text):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.get_style_context().add_class("metric-box")
        
        lbl = Gtk.Label(label=label_text)
        lbl.set_halign(Gtk.Align.CENTER)
        lbl.get_style_context().add_class("metric-label")
        box.pack_start(lbl, False, False, 0)

        val = Gtk.Label(label="–")
        val.get_style_context().add_class("metric-value")
        box.pack_start(val, False, False, 0)

        reset = Gtk.Label(label="")
        reset.get_style_context().add_class("whisper-label")
        box.pack_start(reset, False, False, 0)

        return {"box": box, "val": val, "reset": reset, "lbl": lbl}

    def _on_draw(self, darea, ctx):
        w = darea.get_allocated_width()
        h = darea.get_allocated_height()
        cx, cy = w/2, h/2
        size = min(w, h)
        palette = get_palette()

        if self._pulsing:
            draw_gauge(ctx, cx, cy, size, self.pulse_val, self.pulse_val * 0.7)
            display_util = self.pulse_val
        else:
            draw_gauge(ctx, cx, cy, size, self.five_h_util, self.seven_d_util)
            display_util = max(self.five_h_util, self.seven_d_util)

        # Monochromatic Intensity Logic (Glow as State)
        t = tier(display_util)
        
        # Glow layers
        glow_count = 1 if t == 0 else (2 if t == 1 else 4)
        glow_alpha = 0.08 if t == 0 else (0.12 if t == 1 else 0.15)
        
        # Pulse adjustment for Critical
        if t == 2:
            glow_alpha *= (0.8 + 0.2 * math.sin(datetime.now().timestamp() * 4))

        for i in range(1, glow_count + 1):
            r, g, b = palette["accent"]
            ctx.set_source_rgba(r, g, b, glow_alpha / i)
            ctx.arc(cx, cy, size * (0.1 + i * 0.02), 0, 2 * math.pi)
            ctx.fill()

        # Central Percentage
        ctx.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(size * 0.18)
        
        text = f"{display_util:.0f}%"
        extents = ctx.text_extents(text)
        
        r, g, b = palette["zinc_100"]
        ctx.set_source_rgba(r, g, b, 0.95)
        ctx.move_to(cx - extents.width/2 - extents.x_bearing, cy + extents.height/2)
        ctx.show_text(text)

    def _tick(self):
        if self._pulsing:
            self.pulse_val = (self.pulse_val + 2) % 100
            self.darea.queue_draw()
            return True
            
        lerp_factor = 0.12
        changed = False
        
        if abs(self.target_5h - self.five_h_util) > 0.1:
            self.five_h_util += (self.target_5h - self.five_h_util) * lerp_factor
            changed = True
        else:
            self.five_h_util = self.target_5h
            
        if abs(self.target_7d - self.seven_d_util) > 0.1:
            self.seven_d_util += (self.target_7d - self.seven_d_util) * lerp_factor
            changed = True
        else:
            self.seven_d_util = self.target_7d
            
        # Siempre redibujar para el pulso en crítico
        if tier(max(self.five_h_util, self.seven_d_util)) == 2:
            changed = True

        if changed:
            self.darea.queue_draw()
            
        return True

    def update(self, usage_data=None, error=None, updated_at=None):
        self._pulsing = False

        if error:
            self._status_label.set_markup('<span foreground="#71717A">CONNECTION INTERRUPTED</span>')
            self._whisper_label.set_text(f"ERROR: {error.upper()}")
            return

        if usage_data:
            palette = get_palette()
            new_5h = usage_data.get("five_hour", {}).get("utilization", 0)
            new_7d = usage_data.get("seven_day", {}).get("utilization", 0)
            
            self.target_5h = new_5h
            self.target_7d = new_7d
            
            self._status_label.set_markup(_status_markup(max(new_5h, new_7d)))
            
            # DIARIO (Inner Ring -> Accent)
            color_diario = _hex(palette["accent"])
            self._m_daily["lbl"].set_markup(f'<span foreground="{color_diario}">DIARIO</span>')
            self._m_daily["val"].set_text(f"{new_5h:.0f}%")
            res_5h = usage_data.get("five_hour", {}).get("resets_at", "")
            self._m_daily["reset"].set_text(f"RESETS {format_reset_time(res_5h).upper()}" if res_5h else "")

            # SEMANAL (Outer Ring -> Accent Dim)
            color_semanal = _hex(palette["accent_dim"])
            self._m_weekly["lbl"].set_markup(f'<span foreground="{color_semanal}">SEMANAL</span>')
            self._m_weekly["val"].set_text(f"{new_7d:.0f}%")
            res_7d = usage_data.get("seven_day", {}).get("resets_at", "")
            self._m_weekly["reset"].set_text(f"RESETS {format_reset_time(res_7d).upper()}" if res_7d else "")

    def show(self):
        self.window.present()
