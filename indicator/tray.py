import threading
import warnings
warnings.filterwarnings("ignore", ".*StatusIcon.*", DeprecationWarning)

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk

from datetime import datetime

from .config import POLL_INTERVAL
from .theme import icon_path_for
from .api import read_token, fetch_usage
from .window import UsageWindow


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

        # El menú se construye una sola vez
        self._menu = self._build_menu()

        # Primer fetch inmediato al arrancar, luego cada 30 minutos
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
        """Lanza un fetch en background."""
        if self._fetching:
            return
        if self.last_updated and (datetime.now() - self.last_updated).total_seconds() < 60:
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
        """Guarda los datos obtenidos y actualiza el icono y el tooltip."""
        self.usage_data = data
        self.last_error = None
        self.last_updated = datetime.now()
        five_h = data.get("five_hour", {}).get("utilization", 0)
        seven_d = data.get("seven_day", {}).get("utilization", 0)
        
        # El icono cambia de color basado en el nivel más crítico (el máximo de ambos)
        self.status_icon.set_from_file(icon_path_for(max(five_h, seven_d)))
        self.status_icon.set_tooltip_text(f"Claude 5h:{five_h:.0f}%  7d:{seven_d:.0f}%")

    def _on_fetch_done(self, data, error):
        self._fetching = False
        if not error:
            self._apply_usage_data(data)
        elif "429" in error:
            pass
        else:
            self.last_error = error

        if self.popup_window and self.popup_window.window.get_visible():
            self.popup_window.update(
                usage_data=self.usage_data,
                error=self.last_error,
                updated_at=self.last_updated,
            )
        return False

    def _on_left_click(self, icon):
        if self.popup_window:
            self.popup_window.window.destroy()
        self.popup_window = UsageWindow()
        GLib.idle_add(self._position_popup)
        if self.last_updated and (datetime.now() - self.last_updated).total_seconds() < 60:
            self.popup_window.update(
                usage_data=self.usage_data,
                error=self.last_error,
                updated_at=self.last_updated,
            )
        else:
            self._start_fetch()

    def _position_popup(self):
        if not self.popup_window:
            return False
        win = self.popup_window.window
        ok, _screen, area, _ = self.status_icon.get_geometry()
        if not ok:
            return False
        w, h = win.get_size()
        display = Gdk.Display.get_default()
        monitor = display.get_monitor_at_point(area.x + area.width // 2, area.y + area.height // 2)
        geom = monitor.get_geometry()
        x = max(geom.x, min(area.x, geom.x + geom.width - w))
        if area.y + area.height // 2 < geom.y + geom.height // 2:
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

    def _on_right_click(self, icon, button, activate_time):
        self._menu.popup(
            None, None,
            Gtk.StatusIcon.position_menu,
            icon, button, activate_time,
        )

    def _on_right_click(self, icon, button, activate_time):
        self._menu.popup(
            None, None,
            Gtk.StatusIcon.position_menu,
            icon, button, activate_time,
        )

    def run(self):
        Gtk.main()
