import logging
import threading
import warnings
import sys
from datetime import datetime

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Notify', '0.7')
from gi.repository import Gtk, GLib, Gdk, Gio, Notify

# Desactivar advertencias de StatusIcon ya que GTK3 lo considera deprecado, 
# pero sigue siendo la forma estándar en muchos escritorios Linux.
warnings.filterwarnings("ignore", ".*StatusIcon.*", DeprecationWarning)

from .config import POLL_INTERVAL, _log, get_theme, get_language, get_style, update_setting
from .i18n import t
from .theme import tier, get_menu_css
from .icons import render_pixbuf
from .api import read_token, fetch_usage, format_reset_time
from .window import UsageWindow


class ClaudeWatcher(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.claudeusage.watcher")
        self.usage_data = None
        self.last_error = None
        self.last_updated = None
        self._fetching = False
        self._stale = False
        self.popup_window = None
        self._last_notified_tier = None
        self._current_interval = POLL_INTERVAL
        self._poll_timer_id = None
        
        # Inicializar Notify para notificaciones robustas en Ubuntu/Linux
        Notify.init("Claude Usage Watcher")
        Notify.set_app_name("com.claudeusage.watcher")
        _log.debug("ClaudeWatcher initialized with Notify support")

    def do_activate(self):
        # Mantenemos la aplicación viva aunque no haya ventanas abiertas
        self.hold()
        _log.info("Application activated")

        self.status_icon = Gtk.StatusIcon()
        # Icono inicial vacío (0/0%) desde memoria (Pixbuf)
        self.status_icon.set_from_pixbuf(render_pixbuf(0.0, 0.0))
        self.status_icon.set_tooltip_text(t("tooltip.loading"))
        self.status_icon.connect("activate", self._on_left_click)
        self.status_icon.connect("popup-menu", self._on_right_click)

        self._menu = self._build_menu()

        # Iniciar polling interno
        self._poll_timer_id = GLib.timeout_add_seconds(self._current_interval, self._poll_and_reschedule)

    def _build_menu(self):
        import os as _os
        provider = Gtk.CssProvider()
        # Silence GTK warnings for deprecated properties used for layout
        _devnull = _os.open(_os.devnull, _os.O_WRONLY)
        _saved = _os.dup(2)
        _os.dup2(_devnull, 2)
        try:
            provider.load_from_data(get_menu_css())
        finally:
            _os.dup2(_saved, 2)
            _os.close(_saved)
            _os.close(_devnull)

        menu = Gtk.Menu()
        menu.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        item_refresh = Gtk.MenuItem(label=t("menu.refresh"))
        item_refresh.connect("activate", self._on_refresh_now)
        self._item_refresh = item_refresh
        menu.append(item_refresh)

        # ── Language submenu ──────────────────────────────────
        lang_menu = Gtk.Menu()
        lang_menu.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        item_language = Gtk.MenuItem(label=t("menu.language"))
        item_language.set_submenu(lang_menu)

        current_lang = get_language()
        item_english = Gtk.RadioMenuItem(label=t("menu.english"))
        item_english.set_active(current_lang == "en")
        item_english.connect("activate", self._on_change_language, "en")
        lang_menu.append(item_english)

        item_spanish = Gtk.RadioMenuItem(label=t("menu.spanish"), group=item_english)
        item_spanish.set_active(current_lang == "es")
        item_spanish.connect("activate", self._on_change_language, "es")
        lang_menu.append(item_spanish)

        menu.append(item_language)

        # ── Style submenu ──────────────────────────────────
        style_menu = Gtk.Menu()
        style_menu.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        item_style = Gtk.MenuItem(label=t("menu.style"))
        item_style.set_submenu(style_menu)

        current_style = get_style()
        item_serious = Gtk.RadioMenuItem(label=t("menu.serious"))
        item_serious.set_active(current_style == "serious")
        item_serious.connect("activate", self._on_change_style, "serious")
        style_menu.append(item_serious)

        item_funny = Gtk.RadioMenuItem(label=t("menu.funny"), group=item_serious)
        item_funny.set_active(current_style == "funny")
        item_funny.connect("activate", self._on_change_style, "funny")
        style_menu.append(item_funny)

        menu.append(item_style)

        # ── Design submenu ────────────────────────────────────
        design_menu = Gtk.Menu()
        design_menu.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        item_design = Gtk.MenuItem(label=t("menu.design"))
        item_design.set_submenu(design_menu)

        current_theme = get_theme()
        item_obsidian = Gtk.RadioMenuItem(label=t("menu.obsidian"))
        item_obsidian.set_active(current_theme == "obsidian")
        item_obsidian.connect("activate", self._on_change_theme, "obsidian")
        design_menu.append(item_obsidian)

        item_classic = Gtk.RadioMenuItem(label=t("menu.classic"), group=item_obsidian)
        item_classic.set_active(current_theme == "classic")
        item_classic.connect("activate", self._on_change_theme, "classic")
        design_menu.append(item_classic)

        menu.append(item_design)

        item_open = Gtk.MenuItem(label=t("menu.open_claude"))
        item_open.connect("activate", lambda _: Gio.AppInfo.launch_default_for_uri("https://claude.ai", None))
        menu.append(item_open)

        menu.append(Gtk.SeparatorMenuItem())

        item_quit = Gtk.MenuItem(label=t("menu.quit"))
        item_quit.connect("activate", self._on_quit)
        menu.append(item_quit)

        menu.show_all()
        return menu

    def _on_change_theme(self, widget, theme_name):
        if not widget.get_active():
            return

        if get_theme() == theme_name:
            return

        _log.info(f"Changing theme to {theme_name}")
        update_setting("theme", theme_name)

        # Actualizar icono inmediatamente
        if self.usage_data:
            self._apply_usage_data(self.usage_data)
        else:
            self.status_icon.set_from_pixbuf(render_pixbuf(0.0, 0.0))

        # Si la ventana está abierta, la cerramos para que se recree con el nuevo diseño
        if self.popup_window:
            self.popup_window.window.hide()
            # La recrearemos en el próximo click izquierdo

    def _on_change_style(self, widget, style):
        if not widget.get_active():
            return
        if get_style() == style:
            return

        _log.info(f"Changing style to {style}")
        update_setting("style", style)

        # Rebuild menu (also refreshes self._item_refresh reference)
        self._menu.destroy()
        self._menu = self._build_menu()

        # Destroy popup so construction-time strings are recreated in new style
        if self.popup_window:
            self.popup_window.window.destroy()
            self.popup_window = None

        # Update tooltip in new style
        if self.usage_data:
            self._apply_usage_data(self.usage_data)
        else:
            self.status_icon.set_tooltip_text(t("tooltip.loading"))

    def _on_change_language(self, widget, lang):
        if not widget.get_active():
            return
        # Recursion guard: _build_menu calls set_active(True) which re-fires activate
        if get_language() == lang:
            return

        _log.info(f"Changing language to {lang}")
        update_setting("language", lang)

        # Rebuild menu (also refreshes self._item_refresh reference)
        self._menu.destroy()
        self._menu = self._build_menu()

        # Destroy popup so construction-time strings are recreated in new language
        if self.popup_window:
            self.popup_window.window.destroy()
            self.popup_window = None

        # Update tooltip in new language
        if self.usage_data:
            self._apply_usage_data(self.usage_data)
        else:
            self.status_icon.set_tooltip_text(t("tooltip.loading"))

    def _on_quit(self, _):
        _log.info("Closing application")
        self.quit()
        sys.exit(0)

    def _on_refresh_now(self, _):
        self.last_updated = None  # bypass 60s cooldown
        self._start_fetch()

    def _start_fetch(self):
        """Lanza un fetch en background."""
        if self._fetching:
            return
        # Evitar fetches muy seguidos (excepto si forzamos con refresh now)
        if self.last_updated and (datetime.now() - self.last_updated).total_seconds() < 60:
            return
        
        self._fetching = True
        if hasattr(self, "_item_refresh"):
            self._item_refresh.set_sensitive(False)

        def do_fetch():
            token, err = read_token()
            if err:
                GLib.idle_add(self._on_fetch_done, None, err)
                return
            data, err = fetch_usage(token)
            GLib.idle_add(self._on_fetch_done, data, err)

        threading.Thread(target=do_fetch, daemon=True).start()

    def _poll_and_reschedule(self):
        self._poll_timer_id = None
        self._start_fetch()
        return False

    def _apply_usage_data(self, data):
        """Guarda los datos obtenidos y actualiza el icono y el tooltip."""
        self._stale = False
        self.usage_data = data
        self.last_error = None
        self.last_updated = datetime.now()
        
        five_h = data.get("five_hour", {}).get("utilization", 0)
        seven_d = data.get("seven_day", {}).get("utilization", 0)
        
        # Actualización de icono desde memoria (Pixbuf)
        self.status_icon.set_from_pixbuf(render_pixbuf(five_h, seven_d))
        self.status_icon.set_tooltip_text(t("tooltip.usage", five_h=five_h, seven_d=seven_d))

    def _on_fetch_done(self, data, error):
        self._fetching = False
        if hasattr(self, "_item_refresh"):
            self._item_refresh.set_sensitive(True)

        if not error:
            self._apply_usage_data(data)
            self._check_tier_notifications(data)
        elif "429" in error:
            # Rate limited — mostramos datos cacheados con indicador de desactualización
            self._stale = True
            if self.usage_data:
                five_h = self.usage_data.get("five_hour", {}).get("utilization", 0)
                seven_d = self.usage_data.get("seven_day", {}).get("utilization", 0)
                self.status_icon.set_tooltip_text(
                    t("tooltip.stale", five_h=five_h, seven_d=seven_d)
                )
        else:
            self.last_error = error

        # Calcular próximo intervalo dinámico y reprogramar
        self._current_interval = self._calculate_next_interval(data, error)
        _log.info(f"Next poll scheduled in {self._current_interval} seconds")
        
        if self._poll_timer_id is not None:
            GLib.source_remove(self._poll_timer_id)
        self._poll_timer_id = GLib.timeout_add_seconds(self._current_interval, self._poll_and_reschedule)

        if self.popup_window and self.popup_window.window.get_visible():
            self.popup_window.update(
                usage_data=self.usage_data,
                error=self.last_error,
                updated_at=self.last_updated,
                stale=self._stale,
            )
        return False

    def _calculate_next_interval(self, data, error):
        from .config import MIN_POLL_INTERVAL, MAX_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
        
        # Caso 1: Error 429 (Rate Limit) -> Backoff exponencial
        if error and "429" in str(error):
            # Duplicar el intervalo actual, mínimo 30m, máximo 4h
            next_val = max(self._current_interval * 2, DEFAULT_POLL_INTERVAL)
            return min(next_val, MAX_POLL_INTERVAL)
        
        # Caso 2: Error genérico (Red, etc.) -> Reintento rápido para recuperar
        if error:
            return 150 # 2.5 minutos para reintentar una vez pase el bache
            
        # Caso 3: Éxito -> Adaptar según uso
        if not data:
            return DEFAULT_POLL_INTERVAL
            
        five_h = data.get("five_hour", {}).get("utilization", 0)
        seven_d = data.get("seven_day", {}).get("utilization", 0)
        max_usage = max(five_h, seven_d)
        
        if max_usage > 90:
            return MIN_POLL_INTERVAL # 2.5m - Muy crítico, queremos verlo bajar pronto
        elif max_usage > 70:
            return 450 # 7.5m - Alto riesgo
        elif max_usage < 20:
            return 1800 # 30m - Muy bajo uso, ahorrar tokens
        else:
            return DEFAULT_POLL_INTERVAL # 15m - Normal

    def _check_tier_notifications(self, data):
        five_h = data.get("five_hour", {}).get("utilization", 0)
        seven_d = data.get("seven_day", {}).get("utilization", 0)
        max_util = max(five_h, seven_d)
        current_tier = tier(max_util)

        if self._last_notified_tier is None:
            # Baseline: Always notify on startup to confirm it's working (as requested)
            self._last_notified_tier = current_tier
            self._send_tier_notification(current_tier, five_h, seven_d, data)
        elif current_tier > self._last_notified_tier:
            # Increased risk level
            self._send_tier_notification(current_tier, five_h, seven_d, data)
            self._last_notified_tier = current_tier
        elif current_tier < self._last_notified_tier:
            # Decreased risk level: 
            # 1. Hysteresis (2%) to avoid flapping.
            # 2. Only notify if recovering to 'Normal' (Tier 0).
            thresholds = [0, 60, 85, 95, 100]
            old_threshold = thresholds[self._last_notified_tier]
            
            if max_util < (old_threshold - 2.0):
                if current_tier == 0:
                    self._send_tier_notification(current_tier, five_h, seven_d, data)
                self._last_notified_tier = current_tier

    def _send_tier_notification(self, new_tier, five_h, seven_d, data):
        try:
            reset_str = str(self._best_reset_time(five_h, seven_d, data) or "unknown")
            max_util = max(float(five_h or 0), float(seven_d or 0))

            summary = "Claude Usage Watcher"
            if new_tier >= 4:
                body = t("notif.limit", pct=f"{max_util:.0f}", reset=reset_str)
            elif new_tier == 3:
                body = t("notif.extreme", pct=f"{max_util:.0f}", reset=reset_str)
            elif new_tier == 2:
                body = t("notif.critical", pct=f"{max_util:.0f}", reset=reset_str)
            elif new_tier == 1:
                body = t("notif.warning", pct=f"{max_util:.0f}", reset=reset_str)
            else: # new_tier == 0
                body = t("notif.normal", pct=f"{max_util:.0f}")

            # Ensure body is a valid string
            body = str(body)

            # Icono para la notificación
            import os
            icon_path = os.path.expanduser("~/.cache/claude-usage-watcher/assets/icon_current.png")
            if not os.path.exists(icon_path):
                # Fallback to a standard system icon name if our custom one isn't ready
                icon_path = "dialog-information"

            _log.debug(f"Sending notification: summary='{summary}', body='{body}', icon='{icon_path}', urgency_tier={new_tier}")
            
            # Create notification. All args MUST be strings.
            notif = Notify.Notification.new(summary, body, icon_path)
            
            # IMPORTANTE: Para evitar el warning de Variant NULL en Ubuntu/Gnome,
            # establecemos explícitamente el nombre de la entrada de escritorio.
            notif.set_hint("desktop-entry", GLib.Variant.new_string("com.claudeusage.watcher"))
            
            # Mapeo de prioridades para Notify (libnotify)
            urgency = Notify.Urgency.NORMAL
            if new_tier >= 3:
                urgency = Notify.Urgency.CRITICAL
            elif new_tier == 2:
                urgency = Notify.Urgency.LOW # Warning/Normal
            
            notif.set_urgency(urgency)
            notif.show()
        except Exception as e:
            # Las notificaciones son "best effort"
            _log.warning(f"Failed to send notification via Notify: {e}")

    def _best_reset_time(self, five_h, seven_d, data):
        if five_h >= seven_d:
            resets_at = data.get("five_hour", {}).get("resets_at", "")
        else:
            resets_at = data.get("seven_day", {}).get("resets_at", "")
        return format_reset_time(resets_at) if resets_at else "unknown"

    def _on_left_click(self, icon):
        if self.popup_window:
            self.popup_window.window.destroy()
        self.popup_window = UsageWindow()
        GLib.idle_add(self._position_popup)
        
        # Si los datos están frescos, los mostramos ya
        if self.last_updated and (datetime.now() - self.last_updated).total_seconds() < 60:
            self.popup_window.update(
                usage_data=self.usage_data,
                error=self.last_error,
                updated_at=self.last_updated,
                stale=self._stale,
            )
        else:
            self._start_fetch()

    def _position_popup(self):
        if not self.popup_window:
            return False
            
        win = self.popup_window.window
        ok, _screen, area, _ = self.status_icon.get_geometry()
        
        if not ok:
            # Si el panel aún no está listo (típico al arrancar la sesión), reintentamos en un momento.
            GLib.timeout_add(200, self._position_popup)
            return False
            
        # Calculamos el tamaño preferido antes de mostrarla para saber cuánto mide
        # (win.get_size() devolvería 1x1 si aún no es visible)
        requisition, _ = win.get_preferred_size()
        w, h = requisition.width, requisition.height
        
        display = Gdk.Display.get_default()
        monitor = display.get_monitor_at_point(area.x + area.width // 2, area.y + area.height // 2)
        geom = monitor.get_geometry()
        
        x = max(geom.x, min(area.x, geom.x + geom.width - w))
        
        if area.y + area.height // 2 < geom.y + geom.height // 2:
            y = area.y + area.height + 4
        else:
            y = area.y - h - 4
            
        win.move(x, y)
        win.show_all()
        win.present()
        return False

    def _on_right_click(self, icon, button, activate_time):
        self._menu.popup(
            None, None,
            Gtk.StatusIcon.position_menu,
            icon, button, activate_time,
        )

    def run(self):
        super().run(sys.argv)


def main():
    app = ClaudeWatcher()
    app.run()


if __name__ == "__main__":
    main()
