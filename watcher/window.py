import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk

import cairo
import math
from datetime import datetime

from .theme import get_palette, tier, get_classic_bar_css, utilization_color
from .api import format_reset_time
from .icons import draw_obsidian_gauge
from .config import get_settings

def _hex(rgb):
    return f"#{int(rgb[0]*255):02x}{int(rgb[1]*255):02x}{int(rgb[2]*255):02x}"

# --- Obsidian Design ---

_OBSIDIAN_CSS = b"""
window {
    background-color: #09090B; /* Zinc 950 */
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
}
label {
    color: #F4F4F5; /* Zinc 100 */
    font-family: "Inter", "Cantarell", "Sans";
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

_obsidian_css_provider = None
_classic_css_provider = None
_current_screen_provider = None


def _set_screen_provider(provider):
    """Swap el CSS provider activo en pantalla, removiendo el anterior."""
    global _current_screen_provider
    screen = Gdk.Screen.get_default()
    if _current_screen_provider is not None and _current_screen_provider is not provider:
        Gtk.StyleContext.remove_provider_for_screen(screen, _current_screen_provider)
    if _current_screen_provider is not provider:
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        _current_screen_provider = provider

class ObsidianWindow:
    def __init__(self):
        self.window = Gtk.Window()
        self._apply_theme(self.window)

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
        self.darea.set_tooltip_text("Gauge de uso: cargando…")
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

        self._tick_id = GLib.timeout_add(32, self._tick)

    def _apply_theme(self, window):
        global _obsidian_css_provider
        screen = window.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            window.set_visual(visual)

        if _obsidian_css_provider is None:
            _obsidian_css_provider = Gtk.CssProvider()
            _obsidian_css_provider.load_from_data(_OBSIDIAN_CSS)
        _set_screen_provider(_obsidian_css_provider)

    def _status_markup(self, utilization):
        t = tier(utilization)

        if t == 0:
            label, desc = "SAFE", "All systems operational"
        elif t == 1:
            label, desc = "WARNING", "Approaching limit"
        elif t == 2:
            label, desc = "CRITICAL", "Usage capacity critical"
        else:
            label, desc = "EXTREME", "Limit almost exhausted"

        color = _hex(utilization_color(utilization))
        return f'<span foreground="{color}" weight="bold" size="small">{label}</span>\n<span size="medium" foreground="#F4F4F5">{desc}</span>'

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

        if self._pulsing:
            draw_obsidian_gauge(ctx, cx, cy, size, self.pulse_val, self.pulse_val * 0.7)
            display_util = self.pulse_val
        else:
            draw_obsidian_gauge(ctx, cx, cy, size, self.five_h_util, self.seven_d_util)
            display_util = max(self.five_h_util, self.seven_d_util)

        t = tier(display_util)
        r, g, b = utilization_color(display_util)

        glow_count = 1 if t == 0 else (2 if t == 1 else (4 if t == 2 else 5))
        glow_alpha = 0.08 if t == 0 else (0.12 if t == 1 else (0.15 if t == 2 else 0.22))

        if t >= 2:
            glow_alpha *= (0.8 + 0.2 * math.sin(datetime.now().timestamp() * 4))

        for i in range(1, glow_count + 1):
            ctx.set_source_rgba(r, g, b, glow_alpha / i)
            ctx.arc(cx, cy, size * (0.1 + i * 0.02), 0, 2 * math.pi)
            ctx.fill()

        ctx.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(size * 0.18)

        text = f"{display_util:.0f}%"
        extents = ctx.text_extents(text)

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

        if tier(max(self.five_h_util, self.seven_d_util)) >= 2:
            changed = True  # glow pulse — necesita redraw continuo

        if changed:
            self.darea.queue_draw()
            return True

        # Nada que animar: suspender el timer hasta el próximo update()
        self._tick_id = None
        return False

    def update(self, usage_data=None, error=None, updated_at=None, stale=False):
        self._pulsing = False

        if error:
            self._status_label.set_markup('<span foreground="#71717A">CONNECTION INTERRUPTED</span>')
            return

        if usage_data:
            new_5h = usage_data.get("five_hour", {}).get("utilization", 0)
            new_7d = usage_data.get("seven_day", {}).get("utilization", 0)

            self.target_5h = new_5h
            self.target_7d = new_7d

            # Reactivar el timer si estaba suspendido (valores estables previos)
            if self._tick_id is None:
                self._tick_id = GLib.timeout_add(32, self._tick)

            markup = self._status_markup(max(new_5h, new_7d))
            if stale:
                markup += '\n<span foreground="#71717A" size="small">(datos desactualizados)</span>'
            self._status_label.set_markup(markup)
            self.darea.set_tooltip_text(f"Diario (5h): {new_5h:.0f}%  ·  Semanal (7d): {new_7d:.0f}%")
            
            color_diario = _hex(utilization_color(new_5h))
            self._m_daily["lbl"].set_markup(f'<span foreground="{color_diario}">DIARIO</span>')
            self._m_daily["val"].set_text(f"{new_5h:.0f}%")
            res_5h = usage_data.get("five_hour", {}).get("resets_at", "")
            self._m_daily["reset"].set_text(f"RESETS {format_reset_time(res_5h).upper()}" if res_5h else "")

            color_semanal = _hex(utilization_color(new_7d))
            self._m_weekly["lbl"].set_markup(f'<span foreground="{color_semanal}">SEMANAL</span>')
            self._m_weekly["val"].set_text(f"{new_7d:.0f}%")
            res_7d = usage_data.get("seven_day", {}).get("resets_at", "")
            self._m_weekly["reset"].set_text(f"RESETS {format_reset_time(res_7d).upper()}" if res_7d else "")

    def show(self):
        self.window.show_all()
        self.window.present()

# --- Classic Design ---

_CLASSIC_CSS = b"""
window {
    background-color: #1A1526;
    border: 1px solid rgba(255, 255, 255, 0.09);
}
label {
    color: #E8E2F4;
}
.dim-label {
    color: rgba(232, 226, 244, 0.45);
}
.section-header {
    color: rgba(232, 226, 244, 0.55);
}
progressbar trough {
    background-color: rgba(255, 255, 255, 0.08);
    border-radius: 4px;
    min-height: 8px;
    border: none;
}
progressbar trough progress {
    border-radius: 4px;
    min-height: 8px;
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

_CLASSIC_STATUS = [
    ("#26A269", "All clear"),
    ("#E5A50A", "Approaching limit"),
    ("#C01C28", "Critical usage"),
]

class ClassicWindow:
    def __init__(self):
        self.window = Gtk.Window()
        self._apply_theme(self.window)

        self.window.set_skip_taskbar_hint(True)
        self.window.set_skip_pager_hint(True)
        self.window.set_decorated(False)
        self.window.set_border_width(20)
        self.window.set_resizable(False)
        self.window.connect("focus-out-event", lambda w, e: w.hide() or True)
        self.window.connect("delete-event", lambda w, e: w.hide() or True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.window.add(box)

        self._status_label = Gtk.Label()
        self._status_label.set_markup('<span>–</span>')
        self._status_label.set_halign(Gtk.Align.START)
        box.pack_start(self._status_label, False, False, 0)

        self._five_h = self._make_section("5h")
        box.pack_start(self._five_h["vbox"], False, False, 0)

        self._seven_d = self._make_section("7d")
        box.pack_start(self._seven_d["vbox"], False, False, 0)

        self._ts_label = Gtk.Label(label="Fetching...")
        self._ts_label.set_halign(Gtk.Align.END)
        self._ts_label.get_style_context().add_class("dim-label")
        box.pack_start(self._ts_label, False, False, 0)

        self._pulsing = True
        GLib.timeout_add(80, self._do_pulse)

    def _apply_theme(self, window):
        global _classic_css_provider
        if _classic_css_provider is None:
            _classic_css_provider = Gtk.CssProvider()
            _classic_css_provider.load_from_data(_CLASSIC_CSS)
        _set_screen_provider(_classic_css_provider)

    def _make_section(self, label_text):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        header = Gtk.Label(label=label_text)
        header.set_halign(Gtk.Align.START)
        header.get_style_context().add_class("section-header")
        row.pack_start(header, False, False, 0)

        pct = Gtk.Label()
        pct.set_markup('<span size="xx-large" weight="bold">–</span>')
        pct.set_halign(Gtk.Align.END)
        pct.set_hexpand(True)
        row.pack_start(pct, True, True, 0)

        vbox.pack_start(row, False, False, 0)

        bar = Gtk.ProgressBar()
        bar.set_size_request(280, -1)
        provider = Gtk.CssProvider()
        provider.load_from_data(get_classic_bar_css(0))
        bar.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        vbox.pack_start(bar, False, False, 0)

        reset_lbl = Gtk.Label(label="")
        reset_lbl.set_halign(Gtk.Align.START)
        reset_lbl.get_style_context().add_class("dim-label")
        vbox.pack_start(reset_lbl, False, False, 0)

        return {"vbox": vbox, "pct": pct, "bar": bar, "reset_lbl": reset_lbl, "provider": provider}

    def _do_pulse(self):
        if self._pulsing:
            self._five_h["bar"].pulse()
            self._seven_d["bar"].pulse()
            return True
        return False

    def update(self, usage_data=None, error=None, updated_at=None, stale=False):
        self._pulsing = False

        if error:
            self._status_label.set_markup('<span foreground="#E5A50A">Connection error</span>')
            self._ts_label.set_text(error)
            return

        if usage_data:
            five_h_util = usage_data.get("five_hour", {}).get("utilization", 0)
            seven_d_util = usage_data.get("seven_day", {}).get("utilization", 0)

            color, text = _CLASSIC_STATUS[tier(max(five_h_util, seven_d_util))]
            self._status_label.set_markup(f'<span foreground="{color}">{text}</span>')

            self._fill_section(self._five_h, usage_data.get("five_hour", {}))
            self._fill_section(self._seven_d, usage_data.get("seven_day", {}))

        if updated_at:
            delta = (datetime.now() - updated_at).total_seconds()
            ts = "Updated just now" if delta < 10 else f"Updated {updated_at.strftime('%H:%M')}"
            if stale:
                ts += " (desact.)"
            self._ts_label.set_text(ts)

    def _fill_section(self, section, data):
        utilization = data.get("utilization", 0)
        section["pct"].set_markup(f'<span size="xx-large" weight="bold">{utilization:.0f}%</span>')
        section["bar"].set_fraction(min(utilization / 100.0, 1.0))
        section["provider"].load_from_data(get_classic_bar_css(utilization))
        resets_at = data.get("resets_at", "")
        if resets_at:
            section["reset_lbl"].set_text(f"resets {format_reset_time(resets_at)}")

    def show(self):
        self.window.show_all()
        self.window.present()

# --- Factory ---

def UsageWindow():
    theme = get_settings().get("theme", "obsidian")
    if theme == "classic":
        return ClassicWindow()
    return ObsidianWindow()
