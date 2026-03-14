import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk

import cairo
import math
from datetime import datetime

from .theme import get_palette, tier, arc_color
from .api import format_reset_time
from .icons import draw_gauge

_STATUS = [
    ("Safe", "All systems operational"),
    ("Warning", "Approaching limit"),
    ("Critical", "Usage capacity critical"),
]

def _status_markup(five_h_util, seven_d_util):
    t = tier(max(five_h_util, seven_d_util))
    palette = get_palette()
    color = "#" + "".join(f"{int(c*255):02x}" for c in arc_color(max(five_h_util, seven_d_util)))
    label, desc = _STATUS[t]
    return f'<span foreground="{color}" weight="bold" size="small">{label.upper()}</span>\n<span size="medium">{desc}</span>'

# No eliminar ni editar la parte del menu
_WINDOW_CSS = b"""
window {
    background-color: rgba(10, 10, 12, 0.98);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
}
label {
    color: #E8E2F4;
    font-family: "Inter", "Cantarell", "Sans";
}
.dim-label {
    color: rgba(232, 226, 244, 0.3);
    font-size: 0.75em;
    font-weight: bold;
    letter-spacing: 0.1em;
}
.metric-label {
    color: rgba(232, 226, 244, 0.5);
    font-size: 0.7em;
    font-weight: 800;
    letter-spacing: 0.15em;
}
.metric-value {
    color: #FFFFFF;
    font-size: 1.1em;
    font-weight: bold;
}
menu {
    background-color: #1A1526;
    color: #E8E2F4;
}
menuitem label {
    color: #E8E2F4;
}
menuitem:hover {
    background-color: rgba(255, 255, 255, 0.09);
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

class UsageWindow:
    def __init__(self):
        self.window = Gtk.Window()
        _apply_theme(self.window)

        self.window.set_skip_taskbar_hint(True)
        self.window.set_skip_pager_hint(True)
        self.window.set_decorated(False)
        self.window.set_border_width(28)
        self.window.set_resizable(False)
        self.window.connect("focus-out-event", lambda w, e: w.hide() or True)
        self.window.connect("delete-event", lambda w, e: w.hide() or True)

        self.five_h_util = 0.0
        self.seven_d_util = 0.0
        self.pulse_val = 0.0
        self._pulsing = True

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        self.window.add(main_box)

        # Status Header
        self._status_label = Gtk.Label()
        self._status_label.set_markup('<span foreground="#00F2A6">INITIALIZING</span>')
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

        # Metrics Row
        metrics_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.pack_start(metrics_row, False, False, 0)

        self._m_daily = self._make_metric("DAILY")
        metrics_row.pack_start(self._m_daily["box"], True, True, 0)

        self._m_weekly = self._make_metric("WEEKLY")
        metrics_row.pack_start(self._m_weekly["box"], True, True, 0)

        # Footer
        self._ts_label = Gtk.Label(label="FETCHING DATA...")
        self._ts_label.get_style_context().add_class("dim-label")
        main_box.pack_start(self._ts_label, False, False, 0)

        GLib.timeout_add(40, self._do_pulse)

    def _make_metric(self, label_text):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        
        lbl = Gtk.Label(label=label_text)
        lbl.set_halign(Gtk.Align.CENTER)
        lbl.get_style_context().add_class("metric-label")
        box.pack_start(lbl, False, False, 0)

        val = Gtk.Label(label="–")
        val.get_style_context().add_class("metric-value")
        box.pack_start(val, False, False, 0)

        reset = Gtk.Label(label="")
        reset.get_style_context().add_class("dim-label")
        box.pack_start(reset, False, False, 0)

        return {"box": box, "val": val, "reset": reset}

    def _on_draw(self, darea, ctx):
        w = darea.get_allocated_width()
        h = darea.get_allocated_height()
        cx, cy = w/2, h/2
        size = min(w, h)

        if self._pulsing:
            # Efecto de pulso en carga
            draw_gauge(ctx, cx, cy, size, self.pulse_val, self.pulse_val * 0.7)
        else:
            draw_gauge(ctx, cx, cy, size, self.five_h_util, self.seven_d_util)

        # Dibujar porcentaje central
        max_util = max(self.five_h_util, self.seven_d_util) if not self._pulsing else self.pulse_val
        
        ctx.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(size * 0.18)
        
        text = f"{max_util:.0f}%"
        extents = ctx.text_extents(text)
        
        ctx.set_source_rgba(1, 1, 1, 0.9)
        ctx.move_to(cx - extents.width/2 - extents.x_bearing, cy + extents.height/2)
        ctx.show_text(text)

        # Etiqueta "UTIL" arriba del porcentaje
        ctx.set_font_size(size * 0.05)
        ctx.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        label = "UTILIZATION"
        lext = ctx.text_extents(label)
        ctx.set_source_rgba(1, 1, 1, 0.3)
        ctx.move_to(cx - lext.width/2, cy - size * 0.15)
        ctx.show_text(label)

    def _do_pulse(self):
        if self._pulsing:
            self.pulse_val = (self.pulse_val + 2) % 100
            self.darea.queue_draw()
            return True
        return False

    def update(self, usage_data=None, error=None, updated_at=None):
        self._pulsing = False

        if error:
            self._status_label.set_markup('<span foreground="#FFB800">CONNECTION INTERRUPTED</span>')
            self._ts_label.set_text(f"ERROR: {error.upper()}")
            return

        if usage_data:
            self.five_h_util = usage_data.get("five_hour", {}).get("utilization", 0)
            self.seven_d_util = usage_data.get("seven_day", {}).get("utilization", 0)
            
            self._status_label.set_markup(_status_markup(self.five_h_util, self.seven_d_util))
            
            self._m_daily["val"].set_text(f"{self.five_h_util:.0f}%")
            res_5h = usage_data.get("five_hour", {}).get("resets_at", "")
            self._m_daily["reset"].set_text(format_reset_time(res_5h).upper() if res_5h else "")

            self._m_weekly["val"].set_text(f"{self.seven_d_util:.0f}%")
            res_7d = usage_data.get("seven_day", {}).get("resets_at", "")
            self._m_weekly["reset"].set_text(format_reset_time(res_7d).upper() if res_7d else "")

            self.darea.queue_draw()

        if updated_at:
            delta = (datetime.now() - updated_at).total_seconds()
            ts = "LAST SYNC: JUST NOW" if delta < 10 else f"LAST SYNC: {updated_at.strftime('%H:%M')}"
            self._ts_label.set_text(ts)

    def show(self):
        self.window.present()
