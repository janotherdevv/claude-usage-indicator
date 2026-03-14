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

        # El menú se construye una sola vez — nunca cambia
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
        """Lanza un fetch en background. No hace nada si ya hay uno en curso o los datos son recientes.

        El cooldown de 60 segundos evita saturar la API cuando el usuario abre
        el popup varias veces seguidas (también protege contra el bug conocido
        de 429 en el endpoint /oauth/usage).
        do_fetch corre en un hilo daemon para no bloquear nunca el bucle GTK.
        Los resultados se devuelven via GLib.idle_add, que encola el callback
        en el hilo principal de GTK — desde ahí es seguro tocar widgets de la UI.
        """
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
        self.status_icon.set_from_file(icon_path_for(max(five_h, seven_d)))
        self.status_icon.set_tooltip_text(f"Claude  5h:{five_h:.0f}%  7d:{seven_d:.0f}%")

    def _on_fetch_done(self, data, error):
        # Siempre se ejecuta en el hilo principal de GTK (programado via GLib.idle_add).
        self._fetching = False

        if not error:
            self._apply_usage_data(data)
        elif "429" in error:
            # Rate limit — se ignora silenciosamente y se mantiene el último estado conocido.
            # El endpoint /oauth/usage tiene un bug conocido donde devuelve 429
            # con retry-after: 0, así que mostramos la caché en lugar de un error.
            pass
        else:
            self.last_error = error

        # Actualiza el popup solo si sigue abierto — el usuario puede haberlo
        # cerrado antes de que terminara el fetch.
        if self.popup_window and self.popup_window.window.get_visible():
            self.popup_window.update(
                usage_data=self.usage_data,
                error=self.last_error,
                updated_at=self.last_updated,
            )

        return False  # Eliminar de la cola de idle de GLib

    def _on_left_click(self, icon):
        # Siempre se destruye el popup anterior antes de crear uno nuevo.
        # Esto libera recursos GTK y detiene el temporizador de animación pulse
        # de la ventana vieja, que de lo contrario seguiría disparándose en background.
        if self.popup_window:
            self.popup_window.window.destroy()

        self.popup_window = UsageWindow()
        # Se posiciona después de que la ventana se muestre para que get_size() devuelva dimensiones reales.
        GLib.idle_add(self._position_popup)

        # Si los datos en caché tienen menos de 60 segundos, se muestran directamente
        # sin lanzar otro fetch (evita llamadas innecesarias a la API).
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
        # Usamos la API moderna de Gdk.Display para obtener las dimensiones del monitor
        # en el que está el icono del systray, en lugar del Gdk.Screen deprecado.
        display = Gdk.Display.get_default()
        monitor = display.get_monitor_at_point(area.x + area.width // 2, area.y + area.height // 2)
        geom = monitor.get_geometry()
        # Se limita x para que el popup nunca salga por el borde derecho del monitor.
        x = max(geom.x, min(area.x, geom.x + geom.width - w))
        # Se coloca el popup debajo del icono si está en la mitad superior del
        # monitor (panel superior típico), o encima si está en la mitad inferior.
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
