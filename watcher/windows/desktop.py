import math
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from datetime import datetime

import cairo

from .base import BaseWindow
from ..theme import utilization_color
from ..api import format_reset_time
from ..i18n import t


def _draw_gauge(ctx, widget, cx, cy, r, utilization):
    """Draw a single semicircular fuel gauge at (cx, cy) with radius r.

    Arc geometry (Cairo Y-down: increasing angle = clockwise on screen):
      - Background arc: arc(cx, cy, r, π, 2π)  → left→top→right upward sweep
      - Fill arc: arc(cx, cy, r, π, π + (u/100)*π)
      - Needle angle: π + (u/100)*π; endpoint uses (cx + r*cos(a), cy + r*sin(a))
    """
    style = widget.get_style_context()
    bg = style.get_background_color(Gtk.StateFlags.NORMAL)
    fg = style.get_color(Gtk.StateFlags.NORMAL)

    LINE_W = r * 0.15

    # --- Background arc (full semicircle, system theme color) ---
    ctx.set_source_rgba(bg.red, bg.green, bg.blue, 0.40)
    ctx.set_line_width(LINE_W)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.arc(cx, cy, r, math.pi, 2 * math.pi)
    ctx.stroke()

    # --- Reference tick marks at 25%, 50%, 75% (inside the gauge face) ---
    ctx.set_line_width(r * 0.025)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for frac in (0.25, 0.5, 0.75):
        a = math.pi + frac * math.pi
        cos_a, sin_a = math.cos(a), math.sin(a)
        ctx.set_source_rgba(fg.red, fg.green, fg.blue, 0.18)
        ctx.move_to(cx + r * 0.62 * cos_a, cy + r * 0.62 * sin_a)
        ctx.line_to(cx + r * 0.79 * cos_a, cy + r * 0.79 * sin_a)
        ctx.stroke()

    # --- Fill arc (utilization portion) ---
    if utilization > 0:
        end_angle = math.pi + (min(utilization, 100) / 100.0) * math.pi
        ur, ug, ub = utilization_color(utilization)
        ctx.set_source_rgba(ur, ug, ub, 0.9)
        ctx.set_line_width(LINE_W)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.arc(cx, cy, r, math.pi, end_angle)
        ctx.stroke()

    # --- Needle (stops at 82% of arc radius for a realistic look) ---
    angle = math.pi + (min(utilization, 100) / 100.0) * math.pi
    nx = cx + r * 0.82 * math.cos(angle)
    ny = cy + r * 0.82 * math.sin(angle)
    ur, ug, ub = utilization_color(utilization)
    ctx.set_source_rgba(ur, ug, ub, 1.0)
    ctx.set_line_width(r * 0.04)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.move_to(cx, cy)
    ctx.line_to(nx, ny)
    ctx.stroke()

    # --- Center pivot dot ---
    ctx.set_source_rgba(ur, ug, ub, 1.0)
    ctx.arc(cx, cy, r * 0.07, 0, 2 * math.pi)
    ctx.fill()

    # --- Percentage text (in lower dial face, above pivot) ---
    ctx.set_source_rgba(fg.red, fg.green, fg.blue, 0.9)
    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(r * 0.28)
    text = f"{utilization:.0f}%"
    extents = ctx.text_extents(text)
    ctx.move_to(cx - extents.width / 2 - extents.x_bearing, cy - r * 0.22)
    ctx.show_text(text)


class _GaugeArea(Gtk.DrawingArea):
    """A DrawingArea that renders one semicircular fuel gauge."""
    def __init__(self):
        super().__init__()
        self.utilization = 0.0
        self.set_size_request(200, 115)
        self.connect("draw", self._on_draw)

    def _on_draw(self, widget, ctx):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        cx = w / 2
        cy = h          # center at bottom edge of widget
        r = min(w * 0.45, h * 0.85)
        _draw_gauge(ctx, widget, cx, cy, r, self.utilization)


class DesktopWindow(BaseWindow):
    """GTK-native popup with two stacked Cairo semicircular fuel-gauge dials."""

    def __init__(self, auto_hide=True):
        super().__init__(auto_hide=auto_hide)
        self.window.set_border_width(16)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_size_request(230, -1)
        self.window.add(box)

        # --- Daily (5h) gauge ---
        self._lbl_daily = Gtk.Label()
        self._lbl_daily.set_markup(f'<span size="small" alpha="70%">{t("label.daily")}</span>')
        self._lbl_daily.set_halign(Gtk.Align.CENTER)
        box.pack_start(self._lbl_daily, False, False, 0)

        self._gauge_5h = _GaugeArea()
        box.pack_start(self._gauge_5h, False, False, 0)

        self._reset_5h = Gtk.Label(label="")
        self._reset_5h.set_halign(Gtk.Align.CENTER)
        box.pack_start(self._reset_5h, False, False, 2)

        # --- Weekly (7d) gauge ---
        self._lbl_weekly = Gtk.Label()
        self._lbl_weekly.set_markup(f'<span size="small" alpha="70%">{t("label.weekly")}</span>')
        self._lbl_weekly.set_halign(Gtk.Align.CENTER)
        box.pack_start(self._lbl_weekly, False, False, 0)

        self._gauge_7d = _GaugeArea()
        box.pack_start(self._gauge_7d, False, False, 0)

        self._reset_7d = Gtk.Label(label="")
        self._reset_7d.set_halign(Gtk.Align.CENTER)
        box.pack_start(self._reset_7d, False, False, 2)

        # --- Status / timestamp ---
        self._status_lbl = Gtk.Label(label="")
        self._status_lbl.set_halign(Gtk.Align.CENTER)
        box.pack_start(self._status_lbl, False, False, 0)

    def update(self, usage_data=None, error=None, updated_at=None, stale=False, history=None):
        if error:
            self._status_lbl.set_text(t("classic.conn_error"))
            return

        if usage_data:
            five_h = usage_data.get("five_hour", {}).get("utilization", 0)
            seven_d = usage_data.get("seven_day", {}).get("utilization", 0)

            self._gauge_5h.utilization = five_h
            self._gauge_7d.utilization = seven_d
            self._gauge_5h.queue_draw()
            self._gauge_7d.queue_draw()

            res_5h = usage_data.get("five_hour", {}).get("resets_at", "")
            res_7d = usage_data.get("seven_day", {}).get("resets_at", "")
            self._reset_5h.set_markup(
                f'<span size="small" alpha="60%">{t("label.resets", time=format_reset_time(res_5h))}</span>'
                if res_5h else ""
            )
            self._reset_7d.set_markup(
                f'<span size="small" alpha="60%">{t("label.resets", time=format_reset_time(res_7d))}</span>'
                if res_7d else ""
            )

        if updated_at:
            delta = (datetime.now() - updated_at).total_seconds()
            ts = t("classic.updated_now") if delta < 10 else t("classic.updated_at", time=updated_at.strftime('%H:%M'))
            if stale:
                ts += f" {t('classic.stale_suffix')}"
            self._status_lbl.set_markup(f'<span size="small" alpha="55%">{ts}</span>')
