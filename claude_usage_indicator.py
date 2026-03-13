#!/usr/bin/env python3
"""Claude Usage Indicator — Ubuntu System Tray"""

import json
import math
import time
import threading
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

import cairo

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"
API_URL = "https://api.anthropic.com/api/oauth/usage"
POLL_INTERVAL = 300  # seconds

SCRIPT_DIR = Path(__file__).parent

# Semantic colors (R, G, B) normalized 0–1
_COLOR_GREEN = (0.149, 0.635, 0.412)   # #26A269
_COLOR_AMBER = (0.898, 0.647, 0.039)   # #E5A50A
_COLOR_RED   = (0.753, 0.110, 0.157)   # #C01C28


def _arc_color(utilization):
    if utilization >= 90:
        return _COLOR_RED
    elif utilization >= 70:
        return _COLOR_AMBER
    return _COLOR_GREEN


# Progress bar CSS per state
_CSS_GREEN = b"progressbar > trough > progress { background-color: #26A269; background-image: none; }"
_CSS_AMBER = b"progressbar > trough > progress { background-color: #E5A50A; background-image: none; }"
_CSS_RED   = b"progressbar > trough > progress { background-color: #C01C28; background-image: none; }"


def _bar_css(utilization):
    if utilization >= 90:
        return _CSS_RED
    elif utilization >= 70:
        return _CSS_AMBER
    return _CSS_GREEN


def _render_arc_icon(utilization, size=22):
    """Render a circular progress arc icon. Returns PNG bytes."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surface)

    cx, cy = size / 2, size / 2
    radius = (size / 2) - 2 - 1.5   # 2px margin + half line width
    line_width = 3.0
    start = math.radians(225)        # 7 o'clock
    full_end = math.radians(135)     # 5 o'clock  (270° sweep clockwise)

    ctx.set_line_width(line_width)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)

    # Track base: white at 25% opacity
    ctx.set_source_rgba(1, 1, 1, 0.25)
    ctx.arc(cx, cy, radius, start, full_end)
    ctx.stroke()

    # Colored fill proportional to utilization
    fraction = min(utilization / 100.0, 1.0)
    if fraction > 0:
        fill_end = start + fraction * math.radians(270)
        r, g, b = _arc_color(utilization)
        ctx.set_source_rgb(r, g, b)
        ctx.arc(cx, cy, radius, start, fill_end)
        ctx.stroke()

    import io
    buf = io.BytesIO()
    surface.write_to_png(buf)
    return buf.getvalue()


def _generate_icons():
    """Generate the three representative state icons and save to disk."""
    icons = {
        "icon_ok.png":   45,   # representative green fill
        "icon_warn.png": 80,   # representative amber fill
        "icon_crit.png": 95,   # representative red fill
    }
    for filename, util in icons.items():
        path = SCRIPT_DIR / filename
        path.write_bytes(_render_arc_icon(util))


def read_token():
    try:
        with open(CREDENTIALS_PATH) as f:
            creds = json.load(f)
        oauth = creds["claudeAiOauth"]
        expires_at_ms = oauth.get("expiresAt", 0)
        if expires_at_ms and time.time() * 1000 > expires_at_ms:
            return None, "Token expired"
        return oauth["accessToken"], None
    except FileNotFoundError:
        return None, f"Credentials not found: {CREDENTIALS_PATH}"
    except (KeyError, json.JSONDecodeError) as e:
        return None, f"Credentials parse error: {e}"


def fetch_usage(token):
    req = urllib.request.Request(
        API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        return None, f"HTTP {e.code}: {body[:200]}"
    except urllib.error.URLError as e:
        return None, f"Network error: {e.reason}"
    except Exception as e:
        return None, f"Unexpected error: {e}"


def format_reset_time(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.astimezone().strftime("%a %d %b, %H:%M")
    except Exception:
        return iso_str


def icon_path_for(utilization):
    if utilization >= 90:
        name = "icon_crit.png"
    elif utilization >= 70:
        name = "icon_warn.png"
    else:
        name = "icon_ok.png"
    return str(SCRIPT_DIR / name)


class UsageWindow:
    """Popup window — opens in loading state, updates when fresh data arrives."""

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
        provider.load_from_data(_CSS_GREEN)
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

    def _fill_section(self, section, data):
        utilization = data.get("utilization", 0)
        section["pct"].set_markup(
            f'<span size="xx-large" weight="bold">{utilization:.0f}%</span>'
        )
        section["bar"].set_fraction(min(utilization / 100.0, 1.0))
        section["provider"].load_from_data(_bar_css(utilization))
        resets_at = data.get("resets_at", "")
        if resets_at:
            section["reset_lbl"].set_text(f"Resets: {format_reset_time(resets_at)}")

    def show(self):
        self.window.present()


class ClaudeIndicator:
    def __init__(self):
        self.usage_data = None
        self.last_error = None
        self.last_updated = None
        self._fetching = False
        self.popup_window = None

        self.status_icon = Gtk.StatusIcon()
        self.status_icon.set_from_file(icon_path_for(0))
        self.status_icon.set_tooltip_text("Claude — loading...")
        self.status_icon.connect("activate", self._on_left_click)
        self.status_icon.connect("popup-menu", self._on_right_click)

        # First poll immediately
        self._poll()
        # Then every 5 minutes
        GLib.timeout_add_seconds(POLL_INTERVAL, self._poll_and_reschedule)

    def _build_menu(self):
        menu = Gtk.Menu()
        item_quit = Gtk.MenuItem(label="Quit")
        item_quit.connect("activate", lambda _: Gtk.main_quit())
        menu.append(item_quit)
        menu.show_all()
        return menu

    def _poll(self):
        token, err = read_token()
        if err:
            self.last_error = err
            self._set_icon(0)
            self.status_icon.set_tooltip_text(f"Claude: {err}")
            return

        data, err = fetch_usage(token)
        if err:
            self.last_error = err
            self._set_icon(0)
            self.status_icon.set_tooltip_text("Claude: error")
            return

        self.usage_data = data
        self.last_error = None
        self.last_updated = datetime.now()

        five_h = data.get("five_hour", {}).get("utilization", 0)
        seven_d = data.get("seven_day", {}).get("utilization", 0)
        self._set_icon(max(five_h, seven_d))
        self.status_icon.set_tooltip_text(f"Claude  5h:{five_h:.0f}%  7d:{seven_d:.0f}%")

    def _poll_and_reschedule(self):
        self._poll()
        return True

    def _set_icon(self, utilization):
        self.status_icon.set_from_file(icon_path_for(utilization))

    def _on_left_click(self, icon):
        self.popup_window = UsageWindow()
        GLib.idle_add(self._position_popup)

        if self._fetching:
            return

        self._fetching = True

        def do_fetch():
            token, err = read_token()
            if err:
                GLib.idle_add(self._on_fetch_done, None, err)
                return
            data, err = fetch_usage(token)
            GLib.idle_add(self._on_fetch_done, data, err)

        threading.Thread(target=do_fetch, daemon=True).start()

    def _position_popup(self):
        if not self.popup_window:
            return False
        win = self.popup_window.window
        ok, screen, area, orientation = self.status_icon.get_geometry()
        if not ok:
            return False
        w, h = win.get_size()
        screen_h = screen.get_height()
        screen_w = screen.get_width()
        # Align popup left edge with icon, clamp to screen width
        x = max(0, min(area.x, screen_w - w))
        # Place below icon if panel is at top, above if at bottom
        if area.y < screen_h // 2:
            y = area.y + area.height + 4
        else:
            y = area.y - h - 4
        win.move(x, y)
        return False

    def _on_right_click(self, icon, button, activate_time):
        menu = self._build_menu()
        menu.popup(
            None, None,
            Gtk.StatusIcon.position_menu,
            icon, button, activate_time,
        )

    def _on_fetch_done(self, data, error):
        self._fetching = False
        now = datetime.now()

        if not error:
            self.usage_data = data
            self.last_error = None
            self.last_updated = now
            five_h = data.get("five_hour", {}).get("utilization", 0)
            seven_d = data.get("seven_day", {}).get("utilization", 0)
            self._set_icon(max(five_h, seven_d))
            self.status_icon.set_tooltip_text(f"Claude  5h:{five_h:.0f}%  7d:{seven_d:.0f}%")
        else:
            self.last_error = error

        if self.popup_window and self.popup_window.window.get_visible():
            self.popup_window.update(
                usage_data=self.usage_data,
                error=self.last_error,
                updated_at=self.last_updated,
            )

        return False

    def run(self):
        Gtk.main()


if __name__ == "__main__":
    _generate_icons()
    app = ClaudeIndicator()
    app.run()
