#!/usr/bin/env python3
"""Claude Usage Indicator — Ubuntu System Tray"""

import io
import json
import logging
import math
import time
import threading
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

import cairo

import warnings
warnings.filterwarnings("ignore", ".*StatusIcon.*", DeprecationWarning)

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk

CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"
API_URL = "https://api.anthropic.com/api/oauth/usage"
POLL_INTERVAL = 1800  # segundos (30 minutos)

# Directorio donde vive el script — usado para localizar los PNG de iconos
SCRIPT_DIR = Path(__file__).parent

# --- Logging ------------------------------------------------------------
LOG_PATH = SCRIPT_DIR / "claude_usage_indicator.log"

_log = logging.getLogger("claude_usage")
_log.setLevel(logging.INFO)
_log.addHandler(logging.FileHandler(LOG_PATH, encoding="utf-8"))
_log.addHandler(logging.StreamHandler())
logging.Formatter.default_msec_format = "%s.%03d"
for h in _log.handlers:
    h.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))

# --- Nivel de utilización -----------------------------------------------
# Fuente única de verdad para los tres niveles de umbral (verde / ámbar / rojo).

def _tier(utilization):
    """Devuelve 0=verde, 1=ámbar, 2=rojo para un valor de utilización 0–100."""
    if utilization >= 90:
        return 2
    if utilization >= 70:
        return 1
    return 0

# Las tres listas están indexadas por nivel (0/1/2), así que añadir un nuevo
# nivel solo requiere actualizar _tier() y añadir una entrada a cada lista.
_ARC_COLORS = [
    (0.149, 0.635, 0.412),  # #26A269 verde
    (0.898, 0.647, 0.039),  # #E5A50A ámbar
    (0.753, 0.110, 0.157),  # #C01C28 rojo
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


# --- Generación de iconos -----------------------------------------------

def _render_arc_icon(utilization, size=22):
    """Renderiza un icono de arco de progreso circular. Devuelve bytes PNG.

    El arco barre 270° en sentido horario desde las 7 en punto (225°) hasta
    las 5 en punto (135°). Un track tenue blanco muestra el rango completo;
    el fill de color cubre la proporción correspondiente al valor de utilización.
    """
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surface)

    cx, cy = size / 2, size / 2
    radius = (size / 2) - 2 - 1.5   # 2px margen + mitad del grosor de línea
    start = math.radians(225)        # 7 en punto
    full_end = math.radians(135)     # 5 en punto (270° en sentido horario)

    ctx.set_line_width(3.0)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)

    # Track base: blanco al 25% de opacidad
    ctx.set_source_rgba(1, 1, 1, 0.25)
    ctx.arc(cx, cy, radius, start, full_end)
    ctx.stroke()

    # Fill de color proporcional a la utilización
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
    """Genera los tres iconos de estado representativos y los guarda en disco.

    Usa valores fijos representativos (45 / 80 / 95 %) en lugar del porcentaje
    real — Gtk.StatusIcon requiere un archivo estático en disco y no puede
    renderizar surfaces de Cairo directamente. El porcentaje real se muestra
    en el tooltip y en el popup.
    """
    for name, util in zip(_ICON_NAMES, [45, 80, 95]):
        (SCRIPT_DIR / name).write_bytes(_render_arc_icon(util))


# --- Capa de datos ------------------------------------------------------

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
            data = json.loads(resp.read())
            five_h = data.get("five_hour", {}).get("utilization", "?")
            seven_d = data.get("seven_day", {}).get("utilization", "?")
            _log.info("OK — 5h: %.1f%%  7d: %.1f%%", five_h, seven_d)
            return data, None
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        err = f"HTTP {e.code}: {body[:200]}"
        _log.error(err)
        return None, err
    except urllib.error.URLError as e:
        err = f"Network error: {e.reason}"
        _log.error(err)
        return None, err
    except Exception as e:
        err = f"Unexpected error: {e}"
        _log.error(err)
        return None, err


def format_reset_time(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.astimezone().strftime("%a %d %b, %H:%M")
    except Exception:
        return iso_str


# --- Capa de UI ---------------------------------------------------------

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
        elif not error:
            self._ts_label.set_text("–")

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


# --- Capa de tray -------------------------------------------------------

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


if __name__ == "__main__":
    _generate_icons()
    app = ClaudeIndicator()
    app.run()
