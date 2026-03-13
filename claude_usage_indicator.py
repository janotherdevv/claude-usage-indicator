#!/usr/bin/env python3
"""Claude Usage Indicator — Ubuntu System Tray"""

import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, AppIndicator3, GLib

CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"
API_URL = "https://api.anthropic.com/api/oauth/usage"
POLL_INTERVAL = 300  # seconds

SCRIPT_DIR = Path(__file__).parent


def read_token():
    """Read OAuth token from ~/.claude/.credentials.json"""
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
    """Fetch usage data from Anthropic API. Returns (data_dict, error_str)."""
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
    """Convert ISO reset time to local human-readable string."""
    try:
        dt = datetime.fromisoformat(iso_str)
        local_dt = dt.astimezone()
        return local_dt.strftime("%a %d %b, %H:%M")
    except Exception:
        return iso_str


def icon_path_for(utilization):
    """Return absolute path to icon based on utilization %."""
    if utilization >= 90:
        name = "icon_crit.png"
    elif utilization >= 70:
        name = "icon_warn.png"
    else:
        name = "icon_ok.png"
    return str(SCRIPT_DIR / name)


class UsageWindow:
    """Popup window showing two progress bars."""

    def __init__(self, usage_data, error=None):
        self.window = Gtk.Window(title="Claude Usage")
        self.window.set_border_width(20)
        self.window.set_resizable(False)
        self.window.connect("delete-event", lambda w, e: w.hide() or True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.window.add(box)

        title = Gtk.Label()
        title.set_markup("<b>Claude Usage</b>")
        box.pack_start(title, False, False, 0)

        if error:
            lbl = Gtk.Label(label=f"Error: {error}")
            lbl.set_line_wrap(True)
            box.pack_start(lbl, False, False, 0)
        elif usage_data:
            box.pack_start(self._section("Session (5h)", usage_data.get("five_hour", {})), False, False, 0)
            box.pack_start(Gtk.Separator(), False, False, 4)
            box.pack_start(self._section("Week (7d)", usage_data.get("seven_day", {})), False, False, 0)
        else:
            box.pack_start(Gtk.Label(label="No data yet — updating..."), False, False, 0)

        self.window.show_all()

    def _section(self, label_text, data):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        header = Gtk.Label()
        utilization = data.get("utilization", 0)
        header.set_markup(f"<b>{label_text}</b>  —  {utilization:.1f}%")
        header.set_halign(Gtk.Align.START)
        vbox.pack_start(header, False, False, 0)

        bar = Gtk.ProgressBar()
        bar.set_fraction(min(utilization / 100.0, 1.0))
        bar.set_size_request(320, 20)
        vbox.pack_start(bar, False, False, 0)

        resets_at = data.get("resets_at", "")
        if resets_at:
            reset_lbl = Gtk.Label(label=f"Resets: {format_reset_time(resets_at)}")
            reset_lbl.set_halign(Gtk.Align.START)
            reset_lbl.get_style_context().add_class("dim-label")
            vbox.pack_start(reset_lbl, False, False, 0)

        return vbox

    def show(self):
        self.window.present()


class ClaudeIndicator:
    def __init__(self):
        self.usage_data = None
        self.last_error = None
        self.popup_window = None

        self.indicator = AppIndicator3.Indicator.new(
            "claude-usage",
            str(SCRIPT_DIR / "icon_ok.png"),
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_menu(self._build_menu())

        # First poll immediately
        self._poll()
        # Then every 5 minutes
        GLib.timeout_add_seconds(POLL_INTERVAL, self._poll_and_reschedule)

    def _build_menu(self):
        menu = Gtk.Menu()

        item_open = Gtk.MenuItem(label="Show Usage")
        item_open.connect("activate", self._on_show)
        menu.append(item_open)

        item_refresh = Gtk.MenuItem(label="Refresh Now")
        item_refresh.connect("activate", lambda _: self._poll())
        menu.append(item_refresh)

        menu.append(Gtk.SeparatorMenuItem())

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
            self.indicator.set_title(f"Claude: {err}")
            return

        data, err = fetch_usage(token)
        if err:
            self.last_error = err
            self._set_icon(0)
            self.indicator.set_title(f"Claude: error")
            return

        self.usage_data = data
        self.last_error = None

        five_h = data.get("five_hour", {}).get("utilization", 0)
        seven_d = data.get("seven_day", {}).get("utilization", 0)
        max_util = max(five_h, seven_d)

        self._set_icon(max_util)
        self.indicator.set_title(
            f"Claude  5h:{five_h:.0f}%  7d:{seven_d:.0f}%"
        )

    def _poll_and_reschedule(self):
        self._poll()
        return True  # keep the GLib timer running

    def _set_icon(self, utilization):
        self.indicator.set_icon_full(icon_path_for(utilization), "Claude Usage")

    def _on_show(self, _):
        # Rebuild window with latest data each time
        self.popup_window = UsageWindow(self.usage_data, self.last_error)

    def run(self):
        Gtk.main()


if __name__ == "__main__":
    app = ClaudeIndicator()
    app.run()
