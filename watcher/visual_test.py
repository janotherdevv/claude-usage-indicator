import math
from datetime import datetime, timedelta
from dataclasses import dataclass, field

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, GObject

from .theme import utilization_color
from .window import UsageWindow
from .icons import render_pixbuf
from .i18n import t
from .config import get_theme, update_setting


# ── Simulation State ──────────────────────────────────────────────────────────

@dataclass
class SimulationState:
    sim_5h: float = 0.0        # 0.0 – 1.0
    sim_7d: float = 0.0        # 0.0 – 1.0
    daily_resets: int = 0
    day_history: list = field(default_factory=lambda: [0.0] * 7)
    _base_7d: float = 0.0      # El valor al inicio del día actual

    def step(self, delta: float):
        old_5h = self.sim_5h
        self.sim_5h += delta
        
        # El 7d crece proporcionalmente al avance del 5h durante el día.
        # Ahora un ciclo completo de 5h (1.0) añade un 0.07 (7%) al 7d.
        # De esta forma se requieren 2 ciclos diarios para completar un día de historial (14%).
        growth_factor = 0.07
        self.sim_7d = min(1.0, self._base_7d + (self.sim_5h * growth_factor))

        if self.sim_5h >= 1.0:
            self.sim_5h = 0.0
            self._base_7d = self.sim_7d
            self.daily_resets += 1
            if self.daily_resets % 2 == 0:
                self.day_history = self.day_history[1:] + [self.sim_7d * 100]
        
    def to_usage_data(self) -> dict:
        return {
            "five_hour": {
                "utilization": self.sim_5h * 100,
                "resets_at": (datetime.now() + timedelta(hours=5)).isoformat(),
            },
            "seven_day": {
                "utilization": self.sim_7d * 100,
                "resets_at": (datetime.now() + timedelta(days=7)).isoformat(),
            },
        }

    def get_simulated_history(self) -> list:
        """
        Genera el historial basado en el uso semanal actual.
        Un nuevo dia de historial aparece cada 14% de uso semanal.
        """
        # La secuencia de dias pedida: Domingo(6), Lunes(0), Martes(1)...
        day_sequence = [6, 0, 1, 2, 3, 4, 5]
        usage_pct = self.sim_7d * 100
        days_completed = int(usage_pct // 14)
        
        history = []
        for i in range(min(days_completed, len(day_sequence))):
            # Simulamos que cada dia anterior se pico en un valor fijo progresivo
            history.append((day_sequence[i], (i + 1) * 14))
        return history

    def do_wrap(self):
        """Aplica el ciclo de reset (separado de step para poder pausar en el pico)."""
        self.sim_5h = 0.0
        # Al hacer wrap, el valor actual de 7d se convierte en la nueva base
        self._base_7d = self.sim_7d
        self.daily_resets += 1
        if self.daily_resets % 2 == 0:
            self.day_history = self.day_history[1:] + [self.sim_7d * 100]
        if self.sim_7d >= 1.0:
            self.sim_7d = 0.0
            self._base_7d = 0.0

    def reset(self):
        self.sim_5h = 0.0
        self.sim_7d = 0.0
        self._base_7d = 0.0
        self.daily_resets = 0
        self.day_history = [0.0] * 7


# ── Control Dial ──────────────────────────────────────────────────────────────

class ControlDial(Gtk.DrawingArea):
    __gsignals__ = {
        "simulation-changed": (GObject.SignalFlags.RUN_LAST, None, ())
    }

    def __init__(self, state: SimulationState):
        super().__init__()
        self.state = state
        self._drag_enabled = False
        self._drag_active = False

        self.set_size_request(260, 260)
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )
        self.connect("draw", self._on_draw)
        self.connect("button-press-event", self._on_button_press)
        self.connect("button-release-event", self._on_button_release)
        self.connect("motion-notify-event", self._on_motion_notify)

    def set_drag_enabled(self, enabled: bool):
        self._drag_enabled = enabled

    def _on_draw(self, widget, ctx):
        import cairo
        w = self.get_allocated_width()
        h = self.get_allocated_height()
        cx, cy = w / 2, h / 2
        radius = min(w, h) * 0.37

        # Background — transparent (window handles it)
        ctx.set_source_rgba(0, 0, 0, 0)
        ctx.rectangle(0, 0, w, h)
        ctx.fill()

        # ── Tick marks ──
        for i in range(60):
            a = -math.pi / 2 + i * 2 * math.pi / 60
            is_major = i % 5 == 0
            outer_r = radius + (16 if is_major else 10)
            inner_r = radius + (8 if is_major else 6)
            alpha = 0.35 if is_major else 0.15
            ctx.set_source_rgba(1.0, 1.0, 1.0, alpha)
            ctx.move_to(cx + outer_r * math.cos(a), cy + outer_r * math.sin(a))
            ctx.line_to(cx + inner_r * math.cos(a), cy + inner_r * math.sin(a))
            ctx.set_line_width(1.5 if is_major else 1.0)
            ctx.stroke()

        # ── 7d inner ring ──
        inner_r = radius * 0.66
        ctx.set_source_rgba(1.0, 1.0, 1.0, 0.05)
        ctx.set_line_width(7)
        ctx.arc(cx, cy, inner_r, 0, 2 * math.pi)
        ctx.stroke()

        r7, g7, b7 = utilization_color(self.state.sim_7d * 100)
        if self.state.sim_7d > 0.001:
            ctx.set_source_rgba(r7, g7, b7, 0.55)
            ctx.set_line_width(7)
            ctx.arc(cx, cy, inner_r, -math.pi / 2,
                    -math.pi / 2 + self.state.sim_7d * 2 * math.pi)
            ctx.stroke()

        # ── 5h outer ring ──
        ctx.set_source_rgba(1.0, 1.0, 1.0, 0.06)
        ctx.set_line_width(13)
        ctx.arc(cx, cy, radius, 0, 2 * math.pi)
        ctx.stroke()

        r5, g5, b5 = utilization_color(self.state.sim_5h * 100)
        if self.state.sim_5h > 0.001:
            ctx.set_source_rgba(r5, g5, b5, 0.88)
            ctx.set_line_width(13)
            ctx.arc(cx, cy, radius, -math.pi / 2,
                    -math.pi / 2 + self.state.sim_5h * 2 * math.pi)
            ctx.stroke()

        # ── Needle ──
        needle_a = -math.pi / 2 + self.state.sim_5h * 2 * math.pi
        tip_r = radius + 8
        base_r = radius * 0.25

        # Needle glow
        if self._drag_enabled:
            ctx.set_source_rgba(r5, g5, b5, 0.12)
            ctx.set_line_width(8)
            ctx.move_to(cx + base_r * math.cos(needle_a + math.pi),
                        cy + base_r * math.sin(needle_a + math.pi))
            ctx.line_to(cx + tip_r * math.cos(needle_a),
                        cy + tip_r * math.sin(needle_a))
            ctx.stroke()

        ctx.set_source_rgba(1.0, 1.0, 1.0, 0.85 if self._drag_enabled else 0.5)
        ctx.set_line_width(2)
        ctx.move_to(cx + base_r * math.cos(needle_a + math.pi),
                    cy + base_r * math.sin(needle_a + math.pi))
        ctx.line_to(cx + tip_r * math.cos(needle_a),
                    cy + tip_r * math.sin(needle_a))
        ctx.stroke()

        # ── Center hub ──
        hub_r = 7
        pattern = cairo.RadialGradient(cx, cy, 0, cx, cy, hub_r * 2)
        pattern.add_color_stop_rgba(0, r5, g5, b5, 0.6)
        pattern.add_color_stop_rgba(1, r5, g5, b5, 0.0)
        ctx.set_source(pattern)
        ctx.arc(cx, cy, hub_r * 2, 0, 2 * math.pi)
        ctx.fill()

        ctx.set_source_rgba(0.95, 0.95, 0.96, 1.0)
        ctx.arc(cx, cy, hub_r, 0, 2 * math.pi)
        ctx.fill()

        # ── Center text ──
        try:
            ctx.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        except Exception:
            ctx.select_font_face("Sans", 0, 1)

        # 5h value
        ctx.set_font_size(28)
        t5 = f"{self.state.sim_5h * 100:.0f}%"
        e5 = ctx.text_extents(t5)
        ctx.set_source_rgba(r5, g5, b5, 0.95)
        ctx.move_to(cx - e5.width / 2 - e5.x_bearing, cy - 6)
        ctx.show_text(t5)

        # 7d value
        ctx.set_font_size(11)
        t7 = f"7d · {self.state.sim_7d * 100:.0f}%"
        e7 = ctx.text_extents(t7)
        ctx.set_source_rgba(r7, g7, b7, 0.65)
        ctx.move_to(cx - e7.width / 2 - e7.x_bearing, cy + 20)
        ctx.show_text(t7)

    def _on_button_press(self, widget, event):
        if self._drag_enabled:
            self._drag_active = True
            self._update_from_point(event.x, event.y)
        return True

    def _on_button_release(self, widget, event):
        self._drag_active = False
        return True

    def _on_motion_notify(self, widget, event):
        if self._drag_enabled and self._drag_active:
            self._update_from_point(event.x, event.y)
        return True

    def _update_from_point(self, x, y):
        w = self.get_allocated_width()
        h = self.get_allocated_height()
        cx, cy = w / 2, h / 2
        dx, dy = x - cx, y - cy
        if abs(dx) < 5 and abs(dy) < 5:
            return
        angle = math.atan2(dy, dx)
        self.state.sim_5h = (angle + math.pi / 2) / (2 * math.pi) % 1.0
        self.queue_draw()
        self.emit("simulation-changed")


# ── Control Window ────────────────────────────────────────────────────────────

_CONTROL_CSS = b"""
.visual-test-control {
    background-color: #0D0D12;
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 16px;
}
.visual-test-control label {
    color: #E4E4E7;
    font-family: "Inter", "Cantarell", sans-serif;
}
.wt-header {
    background-color: transparent;
    padding: 0;
}
.wt-title {
    color: rgba(255, 255, 255, 0.28);
    font-size: 0.68em;
    font-weight: 700;
    letter-spacing: 0.14em;
}
.wt-close {
    color: rgba(255, 255, 255, 0.2);
    font-size: 0.9em;
    min-width: 0;
    padding: 0 4px;
    border: none;
    background: transparent;
    border-radius: 50%;
}
.wt-close:hover {
    color: rgba(255, 255, 255, 0.6);
    background-color: rgba(255, 255, 255, 0.08);
}
.badge {
    font-size: 0.62em;
    font-weight: 700;
    letter-spacing: 0.1em;
    border-radius: 4px;
    padding: 2px 8px;
}
.badge-paused {
    color: rgba(255, 255, 255, 0.3);
    background-color: rgba(255, 255, 255, 0.05);
}
.badge-playing {
    color: #F59E0B;
    background-color: rgba(245, 158, 11, 0.12);
}
.badge-manual {
    color: #67E8F9;
    background-color: rgba(103, 232, 249, 0.1);
}
.ctrl-btn {
    background-color: rgba(255, 255, 255, 0.04);
    color: rgba(255, 255, 255, 0.55);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 9px;
    padding: 9px 0;
    font-size: 0.88em;
    min-width: 110px;
}
.ctrl-btn:hover {
    background-color: rgba(255, 255, 255, 0.09);
    color: rgba(255, 255, 255, 0.85);
    border-color: rgba(255, 255, 255, 0.18);
}
.ctrl-btn-play {
    background-color: rgba(245, 158, 11, 0.1);
    color: #F59E0B;
    border-color: rgba(245, 158, 11, 0.3);
}
.ctrl-btn-play:hover {
    background-color: rgba(245, 158, 11, 0.18);
    border-color: rgba(245, 158, 11, 0.55);
}
.ctrl-btn-manual-on {
    background-color: rgba(103, 232, 249, 0.08);
    color: #67E8F9;
    border-color: rgba(103, 232, 249, 0.28);
}
.ctrl-btn-manual-on:hover {
    background-color: rgba(103, 232, 249, 0.14);
}
.visual-test-control .speed-row label {
    color: rgba(255, 255, 255, 0.3);
    font-size: 0.7em;
    letter-spacing: 0.07em;
}
.visual-test-control scale trough {
    background-color: rgba(255, 255, 255, 0.07);
    min-height: 3px;
    border-radius: 2px;
}
.visual-test-control scale trough highlight {
    background-color: rgba(245, 158, 11, 0.5);
    border-radius: 2px;
}
.visual-test-control scale slider {
    background-color: #F59E0B;
    border-radius: 50%;
    min-width: 12px;
    min-height: 12px;
    border: none;
}
.visual-test-control .reset-btn {
    background-color: transparent;
    color: rgba(255, 255, 255, 0.22);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 7px;
    padding: 6px 20px;
    font-size: 0.8em;
    letter-spacing: 0.04em;
}
.visual-test-control .reset-btn:hover {
    color: rgba(255, 255, 255, 0.5);
    border-color: rgba(255, 255, 255, 0.15);
}
.visual-test-control separator {
    background-color: rgba(255, 255, 255, 0.06);
    margin: 2px 0;
}
"""

# Mode constants
MODE_PAUSED = "paused"
MODE_PLAYING = "playing"
MODE_MANUAL = "manual"


class ControlWindow:
    def __init__(self, state: SimulationState, app):
        self._state = state
        self._app = app
        self._mode = MODE_PAUSED

        self.window = Gtk.Window()
        self.window.set_decorated(False)
        self.window.set_resizable(False)
        self.window.set_skip_taskbar_hint(True)
        self.window.connect("delete-event", lambda w, e: app.quit())

        screen = self.window.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.window.set_visual(visual)

        self.window.get_style_context().add_class("visual-test-control")

        provider = Gtk.CssProvider()
        provider.load_from_data(_CONTROL_CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_margin_top(12)
        outer.set_margin_bottom(18)
        outer.set_margin_start(18)
        outer.set_margin_end(18)
        self.window.add(outer)

        # ── Header (drag strip) ──
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header.get_style_context().add_class("wt-header")

        title_lbl = Gtk.Label(label="VISUAL TEST")
        title_lbl.get_style_context().add_class("wt-title")
        title_lbl.set_halign(Gtk.Align.START)
        header.pack_start(title_lbl, True, True, 0)

        # Status badge
        self._badge = Gtk.Label(label="PAUSED")
        self._badge.get_style_context().add_class("badge")
        self._badge.get_style_context().add_class("badge-paused")
        header.pack_start(self._badge, False, False, 8)

        close_btn = Gtk.Button(label="✕")
        close_btn.get_style_context().add_class("wt-close")
        close_btn.connect("clicked", lambda _: app.quit())
        header.pack_start(close_btn, False, False, 0)

        outer.pack_start(header, False, False, 0)

        # Make header the drag handle
        header.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        header.connect("button-press-event",
                       lambda w, e: self.window.begin_move_drag(
                           1, int(e.x_root), int(e.y_root), e.time
                       ) if e.button == 1 else None)

        outer.pack_start(Gtk.Separator(), False, False, 8)

        # ── Dial ──
        self.dial = ControlDial(state)
        dial_box = Gtk.Box()
        dial_box.set_halign(Gtk.Align.CENTER)
        dial_box.set_margin_top(4)
        dial_box.set_margin_bottom(4)
        dial_box.pack_start(self.dial, False, False, 0)
        outer.pack_start(dial_box, False, False, 0)

        outer.pack_start(Gtk.Separator(), False, False, 4)

        # ── Transport controls ──
        transport = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        transport.set_halign(Gtk.Align.CENTER)
        transport.set_margin_top(4)

        self._btn_play = Gtk.Button(label="▶  Play")
        self._btn_play.get_style_context().add_class("ctrl-btn")
        self._btn_play.get_style_context().add_class("ctrl-btn-play")
        self._btn_play.connect("clicked", self._on_play_pause)

        self._btn_manual = Gtk.Button(label="⟲  Manual")
        self._btn_manual.get_style_context().add_class("ctrl-btn")
        self._btn_manual.connect("clicked", self._on_manual)

        self._btn_design = Gtk.Button(label="◈  Design")
        self._btn_design.get_style_context().add_class("ctrl-btn")
        self._btn_design.connect("clicked", lambda _: self._app.toggle_design())

        transport.pack_start(self._btn_play, False, False, 0)
        transport.pack_start(self._btn_manual, False, False, 0)
        transport.pack_start(self._btn_design, False, False, 0)
        outer.pack_start(transport, False, False, 0)

        # ── Speed slider ──
        self._speed_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._speed_box.get_style_context().add_class("speed-row")
        self._speed_box.set_margin_top(10)

        speed_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        speed_lbl = Gtk.Label(label="SPEED")
        speed_lbl.set_halign(Gtk.Align.START)
        speed_header.pack_start(speed_lbl, True, True, 0)
        self._speed_val_lbl = Gtk.Label(label="10 %/s")
        self._speed_val_lbl.set_halign(Gtk.Align.END)
        speed_header.pack_start(self._speed_val_lbl, False, False, 0)
        self._speed_box.pack_start(speed_header, False, False, 0)

        self._speed_slider = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 1, 50, 1
        )
        self._speed_slider.set_value(10)
        self._speed_slider.set_draw_value(False)
        self._speed_slider.connect("value-changed", self._on_speed_changed)
        self._speed_box.pack_start(self._speed_slider, False, False, 0)
        outer.pack_start(self._speed_box, False, False, 0)

        # ── Reset ──
        reset_btn = Gtk.Button(label="Reset")
        reset_btn.get_style_context().add_class("reset-btn")
        reset_btn.set_halign(Gtk.Align.CENTER)
        reset_btn.set_margin_top(10)
        reset_btn.connect("clicked", self._on_reset)
        outer.pack_start(reset_btn, False, False, 0)

        # Permitir arrastrar la ventana desde cualquier punto
        _make_draggable(self.window)

    def get_speed(self) -> float:
        return self._speed_slider.get_value()

    def _on_speed_changed(self, slider):
        v = int(slider.get_value())
        self._speed_val_lbl.set_text(f"{v} %/s")

    def _on_play_pause(self, _btn):
        if self._mode == MODE_PLAYING:
            self._set_mode(MODE_PAUSED)
        else:
            self._set_mode(MODE_PLAYING)

    def _on_manual(self, _btn):
        if self._mode == MODE_MANUAL:
            self._set_mode(MODE_PAUSED)
        else:
            self._set_mode(MODE_MANUAL)

    def _set_mode(self, mode: str):
        self._mode = mode
        sc_play = self._btn_play.get_style_context()
        sc_manual = self._btn_manual.get_style_context()

        # Remove all active state classes
        sc_play.remove_class("ctrl-btn-play")
        sc_manual.remove_class("ctrl-btn-manual-on")

        # Remove badge classes
        sc_badge = self._badge.get_style_context()
        sc_badge.remove_class("badge-paused")
        sc_badge.remove_class("badge-playing")
        sc_badge.remove_class("badge-manual")

        if mode == MODE_PAUSED:
            self._btn_play.set_label("▶  Play")
            sc_play.add_class("ctrl-btn-play")
            sc_badge.add_class("badge-paused")
            self._badge.set_label("PAUSED")
            self._speed_box.set_visible(True)
            self.dial.set_drag_enabled(False)
            self._app.stop_auto()

        elif mode == MODE_PLAYING:
            self._btn_play.set_label("⏸  Pause")
            sc_badge.add_class("badge-playing")
            self._badge.set_label("PLAYING")
            self._speed_box.set_visible(True)
            self.dial.set_drag_enabled(False)
            self._app.start_auto()

        elif mode == MODE_MANUAL:
            self._btn_play.set_label("▶  Play")
            sc_play.add_class("ctrl-btn-play")
            sc_manual.add_class("ctrl-btn-manual-on")
            sc_badge.add_class("badge-manual")
            self._badge.set_label("MANUAL")
            self._speed_box.set_visible(False)
            self.dial.set_drag_enabled(True)
            self._app.stop_auto()

    def _on_reset(self, _btn):
        self._state.reset()
        self.dial.queue_draw()
        self._app.refresh_popup()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_draggable(window):
    """Permite arrastrar una ventana por cualquier zona vacía."""
    window.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
    window.connect(
        "button-press-event",
        lambda w, e: w.begin_move_drag(1, int(e.x_root), int(e.y_root), e.time)
        if e.button == 1 else None,
    )


# ── Visual Test Application ───────────────────────────────────────────────────

class VisualTestApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.claudeusage.visualtest")
        self._auto_timer_id = None

    def run(self):
        super().run(None)

    def do_activate(self):
        self.hold()

        self._state = SimulationState()
        self._control_win = ControlWindow(self._state, self)

        # Tray Icon para el test visual
        self.status_icon = Gtk.StatusIcon()
        self.status_icon.set_from_pixbuf(render_pixbuf(0.0, 0.0))
        self.status_icon.set_tooltip_text("Visual Test Mode")

        # Popup stays visible regardless of focus
        self._popup = UsageWindow(auto_hide=False)
        self._popup.window.connect("delete-event", lambda w, e: self.quit())

        _make_draggable(self._popup.window)

        # Initial render at 0%
        self._popup.update(usage_data=self._state.to_usage_data())

        # Propagate drag changes to popup
        self._control_win.dial.connect(
            "simulation-changed", lambda _d: self.refresh_popup()
        )

        # Show both windows — starts PAUSED, no timer running
        self._control_win.window.show_all()
        self._popup.show()

        GLib.idle_add(self._position_popup)

    def _position_popup(self):
        screen = Gdk.Screen.get_default()
        sw = screen.get_width()
        
        pw, ph = self._popup.window.get_size()
        cw, ch = self._control_win.window.get_size()
        
        margin = 20
        # Posicionar el Popup a la derecha
        px = sw - pw - margin
        py = margin
        self._popup.window.move(px, py)
        
        # Posicionar el Control a la izquierda del Popup
        cx = px - cw - margin
        cy = margin
        self._control_win.window.move(cx, cy)
        return False

    def refresh_popup(self):
        data = self._state.to_usage_data()
        five_h = data["five_hour"]["utilization"]
        seven_d = data["seven_day"]["utilization"]
        
        # Actualizar icono del tray
        self.status_icon.set_from_pixbuf(render_pixbuf(five_h, seven_d))
        self.status_icon.set_tooltip_text(f"Visual Test: {five_h:.0f}% / {seven_d:.0f}%")
        
        self._popup.update(
            usage_data=data,
            history=self._state.get_simulated_history()
        )

    def toggle_design(self):
        current = get_theme()
        _cycle = {"obsidian": "classic", "classic": "desktop", "desktop": "obsidian"}
        new_theme = _cycle.get(current, "obsidian")
        update_setting("theme", new_theme)
        
        # Re-crear popup
        self._popup.window.destroy()
        self._popup = UsageWindow(auto_hide=False)
        self._popup.window.connect("delete-event", lambda w, e: self.quit())
        _make_draggable(self._popup.window)
        
        self.refresh_popup()
        self._popup.show()
        self._position_popup()

    def start_auto(self):
        if self._auto_timer_id is None:
            self._auto_timer_id = GLib.timeout_add(50, self._auto_tick)

    def stop_auto(self):
        if self._auto_timer_id is not None:
            GLib.source_remove(self._auto_timer_id)
            self._auto_timer_id = None

    def _auto_tick(self):
        speed_pct = self._control_win.get_speed()
        delta = (speed_pct / 100.0) * 0.050

        if self._state.sim_5h + delta >= 1.0:
            # Detener en el pico para que se vea el 100%
            self._state.sim_5h = 1.0 - 1e-6
            self._control_win.dial.queue_draw()
            self.refresh_popup()
            self._auto_timer_id = None
            GLib.timeout_add(900, self._wrap_and_resume)
            return False

        self._state.step(delta)
        
        # Comprobar si hemos llegado al 100% semanal para pausar el test
        if self._state.sim_7d >= 1.0:
            self._control_win._set_mode(MODE_PAUSED)
            self.refresh_popup()
            return False

        self._control_win.dial.queue_draw()
        self.refresh_popup()
        return True

    def _wrap_and_resume(self):
        """Tras la pausa en el pico, aplica el wrap y reanuda el timer."""
        self._state.do_wrap()
        self._control_win.dial.queue_draw()
        self.refresh_popup()
        self._auto_timer_id = GLib.timeout_add(50, self._auto_tick)
        return False
