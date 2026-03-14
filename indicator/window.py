import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk

from datetime import datetime

from .theme import bar_css, tier
from .api import format_reset_time

_STATUS = [
    ("#26A269", "All clear"),
    ("#E5A50A", "Approaching limit"),
    ("#C01C28", "Critical usage"),
]


def _status_markup(five_h_util, seven_d_util):
    color, text = _STATUS[tier(max(five_h_util, seven_d_util))]
    return f'<span foreground="{color}">{text}</span>'

_WINDOW_CSS = b"""
window {
    background-color: rgba(26, 21, 38, 0.97);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
}
label {
    color: #E8E2F4;
    font-family: "Inter", "Cantarell", "Sans";
}
.dim-label {
    color: rgba(232, 226, 244, 0.4);
    font-size: 0.9em;
}
.section-header {
    color: rgba(232, 226, 244, 0.5);
    font-weight: bold;
    font-size: 0.85em;
}
progressbar trough {
    background-color: rgba(255, 255, 255, 0.06);
    border-radius: 6px;
    min-height: 10px;
    border: none;
}
progressbar trough progress {
    border-radius: 6px;
    min-height: 10px;
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
    
    # Habilitar transparencia RGBA
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
    """Ventana popup — se abre en estado de carga y se actualiza al llegar datos."""

    def __init__(self):
        self.window = Gtk.Window()
        _apply_theme(self.window)

        # self.window.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.window.set_skip_taskbar_hint(True)
        self.window.set_skip_pager_hint(True)
        self.window.set_decorated(False)
        self.window.set_border_width(24)
        self.window.set_resizable(False)
        self.window.connect("focus-out-event", lambda w, e: w.hide() or True)
        self.window.connect("delete-event", lambda w, e: w.hide() or True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.window.add(box)

        self._status_label = Gtk.Label()
        self._status_label.set_markup('<span>–</span>')
        self._status_label.set_halign(Gtk.Align.START)
        box.pack_start(self._status_label, False, False, 0)

        self._five_h = self._make_section("Diario")
        box.pack_start(self._five_h["vbox"], False, False, 0)

        self._seven_d = self._make_section("Semanal")
        box.pack_start(self._seven_d["vbox"], False, False, 0)

        self._ts_label = Gtk.Label(label="Fetching...")
        self._ts_label.set_halign(Gtk.Align.END)
        self._ts_label.get_style_context().add_class("dim-label")
        box.pack_start(self._ts_label, False, False, 0)

        # Inicia el pulso inmediatamente para que el usuario vea actividad mientras llegan los datos.
        # _do_pulse devuelve False (y se detiene) en cuanto _pulsing pasa a False.
        self._pulsing = True
        GLib.timeout_add(80, self._do_pulse)

    def _make_section(self, label_text):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        header = Gtk.Label(label=label_text)
        header.set_halign(Gtk.Align.START)
        header.set_valign(Gtk.Align.CENTER)
        header.get_style_context().add_class("section-header")
        row.pack_start(header, False, False, 0)

        pct = Gtk.Label()
        pct.set_markup('<span size="xx-large" weight="bold">–</span>')
        pct.set_halign(Gtk.Align.END)
        pct.set_valign(Gtk.Align.CENTER)
        pct.set_hexpand(True)
        row.pack_start(pct, True, True, 0)

        vbox.pack_start(row, False, False, 0)

        bar = Gtk.ProgressBar()
        bar.set_size_request(280, -1)
        provider = Gtk.CssProvider()
        provider.load_from_data(bar_css(0))
        bar.get_style_context().add_provider(
            provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
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

    def update(self, usage_data=None, error=None, updated_at=None):
        self._pulsing = False

        if error:
            self._status_label.set_markup('<span foreground="#E5A50A">Connection error</span>')
            self._ts_label.set_text(error)
            return

        if usage_data:
            five_h_util = usage_data.get("five_hour", {}).get("utilization", 0)
            seven_d_util = usage_data.get("seven_day", {}).get("utilization", 0)
            self._status_label.set_markup(_status_markup(five_h_util, seven_d_util))
            self._fill_section(self._five_h, usage_data.get("five_hour", {}))
            self._fill_section(self._seven_d, usage_data.get("seven_day", {}))

        if updated_at:
            delta = (datetime.now() - updated_at).total_seconds()
            ts = "Updated just now" if delta < 10 else f"Updated {updated_at.strftime('%H:%M')}"
            self._ts_label.set_text(ts)
        elif not error:
            self._ts_label.set_text("–")

    def _fill_section(self, section, data):
        utilization = data.get("utilization", 0)
        section["pct"].set_markup(
            f'<span size="xx-large" weight="bold">{utilization:.0f}%</span>'
        )
        section["bar"].set_fraction(min(utilization / 100.0, 1.0))
        section["provider"].load_from_data(bar_css(utilization))
        resets_at = data.get("resets_at", "")
        if resets_at:
            section["reset_lbl"].set_text(f"resets {format_reset_time(resets_at)}")

    def show(self):
        self.window.present()
