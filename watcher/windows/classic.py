import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import cairo
from datetime import datetime
from pathlib import Path

from .base import BaseWindow, _set_screen_provider, _status_markup, _hex
from ..theme import utilization_color, get_classic_bar_css
from ..api import format_reset_time
from ..history import get_weekly_history
from ..i18n import t

_classic_css_provider = None


class ClassicWindow(BaseWindow):
    def __init__(self, auto_hide=True):
        super().__init__(auto_hide=auto_hide)
        self.history = []

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        # Forzar ancho mínimo del contenido (280px coincide con la barra)
        box.set_size_request(280, -1)
        self.content_area.add(box)

        self._status_label = Gtk.Label()
        self._status_label.set_markup('<span>–</span>')
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.set_valign(Gtk.Align.START)
        self._status_label.set_xalign(0.0)
        self._status_label.set_yalign(0.0) # Anclar al borde superior (Eje Y)
        self._status_label.set_line_wrap(True)
        self._status_label.set_justify(Gtk.Justification.LEFT)
        # Forzar altura fija en píxeles
        self._status_label.set_size_request(-1, 72)
        # Forzar ancho fijo en caracteres
        self._status_label.set_width_chars(38)
        self._status_label.set_max_width_chars(38)
        box.pack_start(self._status_label, False, False, 0)

        self._five_h = self._make_section(t("label.daily"))
        box.pack_start(self._five_h["vbox"], False, False, 0)

        self._seven_d = self._make_section(t("label.weekly"))
        self._seven_d["history_area"].connect("draw", self._on_draw_7d_history)
        box.pack_start(self._seven_d["vbox"], False, False, 0)

        self._ts_label = Gtk.Label(label=t("classic.fetching"))
        self._ts_label.set_halign(Gtk.Align.END)
        self._ts_label.get_style_context().add_class("dim-label")
        box.pack_start(self._ts_label, False, False, 0)

        self._pulsing = True
        GLib.timeout_add(80, self._do_pulse)

    def _apply_theme(self, window):
        global _classic_css_provider
        if _classic_css_provider is None:
            _classic_css_provider = Gtk.CssProvider()
            _classic_css_provider.load_from_path(
                str(Path(__file__).parent.parent / "assets" / "classic.css")
            )
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

        overlay = Gtk.Overlay()

        bar = Gtk.ProgressBar()
        bar.set_size_request(280, 12)
        provider = Gtk.CssProvider()
        provider.load_from_data(get_classic_bar_css(0))
        bar.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # Add margin to top of bar to leave room for history labels
        bar.set_margin_top(15)
        overlay.add(bar)

        history_area = Gtk.DrawingArea()
        # We need the drawing area to be transparent and pass through clicks if any (though we don't have clicks here)
        history_area.set_valign(Gtk.Align.FILL)
        history_area.set_halign(Gtk.Align.FILL)
        overlay.add_overlay(history_area)

        vbox.pack_start(overlay, False, False, 0)

        reset_lbl = Gtk.Label(label="")
        reset_lbl.set_halign(Gtk.Align.START)
        reset_lbl.get_style_context().add_class("dim-label")
        vbox.pack_start(reset_lbl, False, False, 0)

        return {"vbox": vbox, "pct": pct, "bar": bar, "history_area": history_area, "reset_lbl": reset_lbl, "provider": provider}

    def _on_draw_7d_history(self, widget, ctx):
        if not self.history or self._pulsing:
            return False

        width = widget.get_allocated_width()
        height = widget.get_allocated_height()

        bar_y = 15 # Because we set margin_top on the bar
        bar_height = height - bar_y

        for weekday, value in self.history:
            if value <= 0: continue

            x = width * min(value / 100.0, 1.0)
            mr, mg, mb = utilization_color(value)

            # Subtle vertical line cutting the bar
            ctx.set_source_rgb(0.102, 0.082, 0.149) # #1A1526 Classic bg
            ctx.set_line_width(2.0)
            ctx.move_to(x, bar_y)
            ctx.line_to(x, height)
            ctx.stroke()

            # Glowing node
            ctx.new_path()
            ctx.arc(x, bar_y + bar_height / 2, 4, 0, 2 * 3.14159)
            ctx.set_source_rgba(mr, mg, mb, 1.0)
            ctx.fill()

            ctx.new_path()
            ctx.arc(x, bar_y + bar_height / 2, 4, 0, 2 * 3.14159)
            ctx.set_source_rgba(0.102, 0.082, 0.149, 0.8) # Inner dark dot for bead effect matching bg
            ctx.set_line_width(1.0)
            ctx.stroke()

            # Draw letter floating above
            day_letter = t(f"day.{weekday}")
            ctx.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            ctx.set_font_size(10)

            extents = ctx.text_extents(day_letter)
            ctx.set_source_rgba(mr, mg, mb, 0.95)
            # Center text over x, and place it above the bar
            ctx.move_to(x - extents.width/2 - extents.x_bearing, bar_y - 4)
            ctx.show_text(day_letter)

        return False

    def _do_pulse(self):
        if self._pulsing:
            self._five_h["bar"].pulse()
            self._seven_d["bar"].pulse()
            return True
        return False

    def update(self, usage_data=None, error=None, updated_at=None, stale=False, history=None):
        self._pulsing = False

        if history is not None:
            self.history = history
        elif not self.history:
            from ..history import get_weekly_history
            self.history = get_weekly_history()

        if usage_data:
            five_h_util = usage_data.get("five_hour", {}).get("utilization", 0)
            seven_d_util = usage_data.get("seven_day", {}).get("utilization", 0)

            if error:
                self._status_label.set_markup(f'<span foreground="#E5A50A" weight="bold">{t("status.interrupted")}</span>\n<span foreground="#A1A1AA" size="small">{t("status.interact_to_activate")}</span>')
            else:
                dominant = max(five_h_util, seven_d_util)
                self._status_label.set_markup(_status_markup(dominant, text_color="#E8E2F4"))

            self._fill_section(self._five_h, usage_data.get("five_hour", {}))
            self._fill_section(self._seven_d, usage_data.get("seven_day", {}))
        elif error:
            self._status_label.set_markup(f'<span foreground="#E5A50A" weight="bold">{t("status.interrupted")}</span>\n<span foreground="#A1A1AA" size="small">{t("status.interact_to_activate")}</span>')

        if updated_at:
            delta = (datetime.now() - updated_at).total_seconds()
            ts = t("shared.updated_now") if delta < 10 else t("shared.updated_at", time=updated_at.strftime('%H:%M'))
            if stale:
                ts += f" {t('shared.stale_suffix')}"
            self._ts_label.set_text(ts)

    def _fill_section(self, section, data):
        utilization = data.get("utilization", 0)
        color = _hex(utilization_color(utilization))
        section["pct"].set_markup(f'<span size="xx-large" weight="bold" foreground="{color}">{utilization:.0f}%</span>')
        section["bar"].set_fraction(min(utilization / 100.0, 1.0))
        section["provider"].load_from_data(get_classic_bar_css(utilization))
        resets_at = data.get("resets_at", "")
        if resets_at:
            section["reset_lbl"].set_text(t("classic.resets", time=format_reset_time(resets_at)))
        else:
            section["reset_lbl"].set_text("")
