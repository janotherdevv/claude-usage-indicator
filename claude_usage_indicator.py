#!/usr/bin/env python3
"""Claude Usage Indicator — Ubuntu System Tray"""

import io
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
POLL_INTERVAL = 1800  # seconds (30 minutes)

SCRIPT_DIR = Path(__file__).parent

# --- Utilization tier ---------------------------------------------------
# Single source of truth for the three threshold tiers (green / amber / red).

def _tier(utilization):
    """Return 0=green, 1=amber, 2=red for a utilization value 0–100."""
    if utilization >= 90:
        return 2
    if utilization >= 70:
        return 1
    return 0

_ARC_COLORS = [
    (0.149, 0.635, 0.412),  # #26A269 green
    (0.898, 0.647, 0.039),  # #E5A50A amber
    (0.753, 0.110, 0.157),  # #C01C28 red
]
_BAR_CSS = [
    b"progressbar > trough > progress { background-color: #26A269; background-image: none; }",
    b"progressbar > trough > progress { background-color: #E5A50A; background-image: none; }",
    b"progressbar > trough > progress { background-color: #C01C28; background-image: none; }",
]
_ICON_NAMES = ["icon_ok.png", "icon_warn.png", "icon_crit.png"]


def _arc_color(utilization):
    return _ARC_COLORS[_tier(utilization)]

def _bar_css(utilization):
    return _BAR_CSS[_tier(utilization)]

def icon_path_for(utilization):
    return str(SCRIPT_DIR / _ICON_NAMES[_tier(utilization)])


# --- Icon generation ----------------------------------------------------

def _render_arc_icon(utilization, size=22):
    """Render a circular progress arc icon. Returns PNG bytes."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surface)

    cx, cy = size / 2, size / 2
    radius = (size / 2) - 2 - 1.5   # 2px margin + half line width
    start = math.radians(225)        # 7 o'clock
    full_end = math.radians(135)     # 5 o'clock (270° sweep clockwise)

    ctx.set_line_width(3.0)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)

    # Track base: white at 25% opacity
    ctx.set_source_rgba(1, 1, 1, 0.25)
    ctx.arc(cx, cy, radius, start, full_end)
    ctx.stroke()

    # Colored fill proportional to utilization
    fraction = min(utilization / 100.0, 1.0)
    if fraction > 0:
        r, g, b = _arc_color(utilization)
        ctx.set_source_rgb(r, g, b)
        ctx.arc(cx, cy, radius, start, start + fraction * math.radians(270))
        ctx.stroke()

    buf = io.BytesIO()
    surface.write_to_png(buf)
    return buf.getvalue()


def _generate_icons():
    """Generate the three representative state icons and save to disk."""
    for name, util in zip(_ICON_NAMES, [45, 80, 95]):
        (SCRIPT_DIR / name).write_bytes(_render_arc_icon(util))


# --- Data layer ---------------------------------------------------------

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


# --- UI layer -----------------------------------------------------------

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
        provider.load_from_data(_BAR_CSS[0])
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


# --- Tray layer ---------------------------------------------------------

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

        # Build menu once — it never changes
        self._menu = self._build_menu()

        # First poll immediately (async), then every 5 minutes
        self._start_fetch()
        GLib.timeout_add_seconds(POLL_INTERVAL, self._poll_and_reschedule)

    def _build_menu(self):
        menu = Gtk.Menu()
        item_quit = Gtk.MenuItem(label="Quit")
        item_quit.connect("activate", lambda _: Gtk.main_quit())
        menu.append(item_quit)
        menu.show_all()
        return menu

    def _start_fetch(self):
        """Launch a background fetch. No-op if one is already in flight."""
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

    def _poll_and_reschedule(self):
        self._start_fetch()
        return True

    def _apply_usage_data(self, data):
        """Store fetched data and update icon + tooltip."""
        self.usage_data = data
        self.last_error = None
        self.last_updated = datetime.now()
        five_h = data.get("five_hour", {}).get("utilization", 0)
        seven_d = data.get("seven_day", {}).get("utilization", 0)
        self.status_icon.set_from_file(icon_path_for(max(five_h, seven_d)))
        self.status_icon.set_tooltip_text(f"Claude  5h:{five_h:.0f}%  7d:{seven_d:.0f}%")

    def _on_fetch_done(self, data, error):
        self._fetching = False

        if not error:
            self._apply_usage_data(data)
        else:
            self.last_error = error

        if self.popup_window and self.popup_window.window.get_visible():
            self.popup_window.update(
                usage_data=self.usage_data,
                error=self.last_error,
                updated_at=self.last_updated,
            )

        return False  # Remove from GLib idle queue

    def _on_left_click(self, icon):
        # Destroy previous window (frees GTK resources and stops its pulse timer)
        if self.popup_window:
            self.popup_window.window.destroy()

        self.popup_window = UsageWindow()
        GLib.idle_add(self._position_popup)
        self._start_fetch()

    def _position_popup(self):
        if not self.popup_window:
            return False
        win = self.popup_window.window
        ok, screen, area, _ = self.status_icon.get_geometry()
        if not ok:
            return False
        w, h = win.get_size()
        x = max(0, min(area.x, screen.get_width() - w))
        if area.y < screen.get_height() // 2:
            y = area.y + area.height + 4
        else:
            y = area.y - h - 4
        win.move(x, y)
        return False

    def _on_right_click(self, icon, button, activate_time):
        self._menu.popup(
            None, None,
            Gtk.StatusIcon.position_menu,
            icon, button, activate_time,
        )

    def run(self):
        Gtk.main()


if __name__ == "__main__":
    _generate_icons()
    app = ClaudeIndicator()
    app.run()
