import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import cairo
import math
from datetime import datetime
from pathlib import Path

from .base import BaseWindow, _set_screen_provider, _status_markup, _hex
from ..theme import tier, utilization_color, get_palette
from ..api import format_reset_time
from ..icons import draw_obsidian_gauge
from ..history import get_weekly_history
from ..i18n import t

_obsidian_css_provider = None


class ObsidianWindow(BaseWindow):
    def __init__(self, auto_hide=True):
        super().__init__(auto_hide=auto_hide)

        self.five_h_util = 0.0
        self.seven_d_util = 0.0
        self.history = []
        self.target_5h = 0.0
        self.target_7d = 0.0
        self.pulse_val = 0.0
        self._pulsing = True

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        # Forzar ancho mínimo del contenido (200px coincide con el gauge)
        main_box.set_size_request(200, -1)
        self.window.add(main_box)

        # Status Header
        self._status_label = Gtk.Label()
        self._status_label.set_markup(f'<span foreground="#71717A" weight="bold">{t("status.initializing")}</span>')
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.set_valign(Gtk.Align.START)
        self._status_label.set_xalign(0.0)
        self._status_label.set_yalign(0.0) # Anclar al borde superior (Eje Y)
        self._status_label.set_line_wrap(True)
        self._status_label.set_justify(Gtk.Justification.LEFT)
        # Forzar una altura fija en píxeles
        self._status_label.set_size_request(-1, 64)
        # Forzar ancho fijo en caracteres
        self._status_label.set_width_chars(28)
        self._status_label.set_max_width_chars(28)
        main_box.pack_start(self._status_label, False, False, 0)

        # Gauge Container
        gauge_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.darea = Gtk.DrawingArea()
        self.darea.set_size_request(200, 200)
        self.darea.set_tooltip_text(t("label.gauge_loading"))
        self.darea.connect("draw", self._on_draw)
        gauge_box.pack_start(self.darea, True, True, 0)
        main_box.pack_start(gauge_box, True, True, 0)

        # Metrics Column (Legend and Details)
        metrics_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.pack_start(metrics_col, False, False, 0)

        self._m_daily = self._make_metric(t("label.daily"))
        metrics_col.pack_start(self._m_daily["box"], False, False, 0)

        self._m_weekly = self._make_metric(t("label.weekly"))
        metrics_col.pack_start(self._m_weekly["box"], False, False, 0)

        self._tick_id = GLib.timeout_add(32, self._tick)

    def _apply_theme(self, window):
        global _obsidian_css_provider
        if _obsidian_css_provider is None:
            _obsidian_css_provider = Gtk.CssProvider()
            _obsidian_css_provider.load_from_path(
                str(Path(__file__).parent.parent / "assets" / "obsidian.css")
            )
        _set_screen_provider(_obsidian_css_provider)

    def _status_markup(self, utilization):
        return _status_markup(utilization, text_color="#F4F4F5")

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
            draw_obsidian_gauge(ctx, cx, cy, size, self.pulse_val, self.pulse_val * 0.7, history=self.history)
            display_util = self.pulse_val
        else:
            draw_obsidian_gauge(ctx, cx, cy, size, self.five_h_util, self.seven_d_util, history=self.history)
            display_util = max(self.five_h_util, self.seven_d_util)

        tr = tier(display_util)
        r, g, b = utilization_color(display_util)

        glow_count = 1 if tr == 0 else (2 if tr == 1 else (4 if tr == 2 else 5))
        glow_alpha = 0.08 if tr == 0 else (0.12 if tr == 1 else (0.15 if tr == 2 else 0.22))

        if tr >= 2:
            glow_alpha *= (0.8 + 0.2 * math.sin(datetime.now().timestamp() * 4))

        for i in range(1, glow_count + 1):
            ctx.set_source_rgba(r, g, b, glow_alpha / i)
            ctx.arc(cx, cy, size * (0.1 + i * 0.02), 0, 2 * math.pi)
            ctx.fill()

        ctx.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(size * 0.18)

        text = f"{display_util:.0f}%"

        # Factor de transición suave para el 90% -> 100%
        # Esto elimina el salto brusco de tamaño y color
        t_factor = max(0.0, min(1.0, (display_util - 90) / 10.0))

        # Tamaño de fuente interpolado (0.18 -> 0.155)
        font_size_mult = 0.18 - (t_factor * 0.025)
        ctx.set_font_size(size * font_size_mult)

        extents = ctx.text_extents(text)
        tx = cx - extents.width/2 - extents.x_bearing
        ty = cy + extents.height/2

        # Propuesta 2: Halo Ultra-Fino (Invisible/Ethereal)
        # La opacidad del halo aumenta con el factor de transición
        bg_r, bg_g, bg_b = get_palette()["bg"]
        ctx.set_source_rgba(bg_r, bg_g, bg_b, 0.4 + (t_factor * 0.25))
        ctx.set_line_width(size * 0.012)
        ctx.move_to(tx, ty)
        ctx.text_path(text)
        ctx.stroke()

        # Color de texto interpolado (Armonía profunda)
        # Transicionamos de (r, g, b) brillante a (r*0.1, g*0.1, b*0.1) casi negro
        text_r = r * (1.0 - (t_factor * 0.9))
        text_g = g * (1.0 - (t_factor * 0.9))
        text_b = b * (1.0 - (t_factor * 0.9))

        ctx.set_source_rgba(text_r, text_g, text_b, 0.95 + (t_factor * 0.03))

        ctx.move_to(tx, ty)
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

    def update(self, usage_data=None, error=None, updated_at=None, stale=False, history=None):
        self._pulsing = False

        if history is not None:
            self.history = history
        elif not self.history:
            self.history = get_weekly_history()

        if usage_data:
            new_5h = usage_data.get("five_hour", {}).get("utilization", 0)
            new_7d = usage_data.get("seven_day", {}).get("utilization", 0)

            self.target_5h = new_5h
            self.target_7d = new_7d

            # Reactivar el timer si estaba suspendido (valores estables previos)
            if self._tick_id is None:
                self._tick_id = GLib.timeout_add(32, self._tick)

            if error:
                markup = f'<span foreground="#EF4444" weight="bold">{t("status.interrupted")}</span>\n<span foreground="#71717A" size="small">{t("status.interact_to_activate")}</span>'
            else:
                markup = self._status_markup(max(new_5h, new_7d))
                if stale:
                    markup += f'\n<span foreground="#71717A" size="small">{t("label.stale")}</span>'
            self._status_label.set_markup(markup)
            self.darea.set_tooltip_text(t("label.gauge_tooltip", five_h=new_5h, seven_d=new_7d))

            color_diario = _hex(utilization_color(new_5h))
            self._m_daily["lbl"].set_markup(f'<span foreground="{color_diario}">{t("label.daily")}</span>')
            self._m_daily["val"].set_text(f"{new_5h:.0f}%")
            res_5h = usage_data.get("five_hour", {}).get("resets_at", "")
            self._m_daily["reset"].set_text(t("label.resets", time=format_reset_time(res_5h).upper()) if res_5h else "")

            color_semanal = _hex(utilization_color(new_7d))
            self._m_weekly["lbl"].set_markup(f'<span foreground="{color_semanal}">{t("label.weekly")}</span>')
            self._m_weekly["val"].set_text(f"{new_7d:.0f}%")
            res_7d = usage_data.get("seven_day", {}).get("resets_at", "")
            self._m_weekly["reset"].set_text(t("label.resets", time=format_reset_time(res_7d).upper()) if res_7d else "")
        elif error:
            self._status_label.set_markup(f'<span foreground="#EF4444" weight="bold">{t("status.interrupted")}</span>\n<span foreground="#71717A" size="small">{t("status.interact_to_activate")}</span>')
