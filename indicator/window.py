import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from datetime import datetime

from .theme import bar_css
from .api import format_reset_time


class UsageWindow:
    """Ventana popup — se abre en estado de carga y se actualiza al llegar datos."""

    def __init__(self):
        self.window = Gtk.Window()
        self.window.set_decorated(False)
        self.window.set_border_width(16)
        self.window.set_resizable(False)
        self.window.connect("focus-out-event", lambda w, e: w.hide() or True)
        self.window.connect("delete-event", lambda w, e: w.hide() or True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.window.add(box)

        title = Gtk.Label()
        title.set_markup("<b>Claude Usage</b>")
        title.set_halign(Gtk.Align.START)
        box.pack_start(title, False, False, 0)

        self._five_h = self._make_section("Session (5h)")
        box.pack_start(self._five_h["vbox"], False, False, 0)

        box.pack_start(Gtk.Separator(), False, False, 0)

        self._seven_d = self._make_section("Week (7d)")
        box.pack_start(self._seven_d["vbox"], False, False, 0)

        self._ts_label = Gtk.Label(label="Fetching...")
        self._ts_label.set_halign(Gtk.Align.END)
        self._ts_label.get_style_context().add_class("dim-label")
        box.pack_start(self._ts_label, False, False, 0)

        # Inicia el pulso inmediatamente para que el usuario vea actividad mientras llegan los datos.
        # _do_pulse devuelve False (y se detiene) en cuanto _pulsing pasa a False.
        self._pulsing = True
        GLib.timeout_add(80, self._do_pulse)

        self.window.show_all()

    def _make_section(self, label_text):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        header = Gtk.Label()
        header.set_markup(f"<b>{label_text}</b>")
        header.set_halign(Gtk.Align.START)
        vbox.pack_start(header, False, False, 0)

        pct = Gtk.Label()
        pct.set_markup('<span size="xx-large" weight="bold">–</span>')
        pct.set_halign(Gtk.Align.START)
        vbox.pack_start(pct, False, False, 0)

        bar = Gtk.ProgressBar()
        bar.set_size_request(308, 14)
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
            self._ts_label.set_text(f"Error: {error}")
            return

        if usage_data:
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
            section["reset_lbl"].set_text(f"Resets: {format_reset_time(resets_at)}")

    def show(self):
        self.window.present()
