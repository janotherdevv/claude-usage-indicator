import logging
import threading
import warnings
import sys
from datetime import datetime

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk, Gio

# Desactivar advertencias de StatusIcon ya que GTK3 lo considera deprecado, 
# pero sigue siendo la forma estándar en muchos escritorios Linux.
warnings.filterwarnings("ignore", ".*StatusIcon.*", DeprecationWarning)

from .config import POLL_INTERVAL, _log, get_theme, get_language, update_setting
from .i18n import t
from .theme import tier
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
        _log.debug("ClaudeWatcher initialized")

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

        # Primer fetch inmediato, luego cada POLL_INTERVAL
        self._start_fetch()
        GLib.timeout_add_seconds(POLL_INTERVAL, self._poll_and_reschedule)

    def _build_menu(self):
        import os as _os
        _submenu_css = b"menu { -GtkMenu-double-arrows: 0; } menu > arrow { min-height: 0; min-width: 0; opacity: 0; }"

        def _make_submenu_provider():
            prov = Gtk.CssProvider()
            devnull = _os.open(_os.devnull, _os.O_WRONLY)
            saved = _os.dup(2)
            _os.dup2(devnull, 2)
            try:
                prov.load_from_data(_submenu_css)
            finally:
                _os.dup2(saved, 2)
                _os.close(saved)
                _os.close(devnull)
            return prov

        menu = Gtk.Menu()

        item_refresh = Gtk.MenuItem(label=t("menu.refresh"))
        item_refresh.connect("activate", self._on_refresh_now)
        self._item_refresh = item_refresh
        menu.append(item_refresh)

        # ── Language submenu ──────────────────────────────────
        lang_menu = Gtk.Menu()
        item_language = Gtk.MenuItem(label=t("menu.language"))
        item_language.set_submenu(lang_menu)
        lang_menu.get_style_context().add_provider(_make_submenu_provider(), Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

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

        # ── Design submenu ────────────────────────────────────
        design_menu = Gtk.Menu()
        item_design = Gtk.MenuItem(label=t("menu.design"))
        item_design.set_submenu(design_menu)
        design_menu.get_style_context().add_provider(_make_submenu_provider(), Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

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
            five_h = self.usage_data.get("five_hour", {}).get("utilization", 0)
            seven_d = self.usage_data.get("seven_day", {}).get("utilization", 0)
            if self._stale:
                self.status_icon.set_tooltip_text(t("tooltip.stale", five_h=five_h, seven_d=seven_d))
            else:
                self.status_icon.set_tooltip_text(t("tooltip.usage", five_h=five_h, seven_d=seven_d))
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
        self._start_fetch()
        return True

    def _apply_usage_data(self, data):
        """Guarda los datos obtenidos y actualiza el icono y el tooltip."""
        self._stale = False
        self.usage_data = data
        self.last_error = None
        self.last_updated = datetime.now()
        
        five_h = data.get("five_hour", {}).get("utilization", 0)
        seven_d = data.get("seven_day", {}).get("utilization", 0)
        max_util = max(five_h, seven_d)
        
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

        if self.popup_window and self.popup_window.window.get_visible():
            self.popup_window.update(
                usage_data=self.usage_data,
                error=self.last_error,
                updated_at=self.last_updated,
                stale=self._stale,
            )
        return False

    def _check_tier_notifications(self, data):
        five_h = data.get("five_hour", {}).get("utilization", 0)
        seven_d = data.get("seven_day", {}).get("utilization", 0)
        current_tier = tier(max(five_h, seven_d))

        if self._last_notified_tier is None:
            # Primera ejecución, establecemos baseline
            self._last_notified_tier = current_tier
        elif current_tier != self._last_notified_tier:
            self._send_tier_notification(current_tier, five_h, seven_d, data)
            self._last_notified_tier = current_tier

    def _send_tier_notification(self, new_tier, five_h, seven_d, data):
        try:
            notif = Gio.Notification.new("Claude Usage Watcher")
            reset_str = self._best_reset_time(five_h, seven_d, data)
            max_util = max(five_h, seven_d)

            if max_util >= 100:
                body = t("notif.extreme", pct=f"{max_util:.0f}", reset=reset_str)
            elif new_tier == 0:
                body = t("notif.normal", pct=f"{max_util:.0f}")
            elif new_tier == 1:
                body = t("notif.warning", pct=f"{max_util:.0f}", reset=reset_str)
            elif new_tier == 2:
                body = t("notif.critical", pct=f"{max_util:.0f}", reset=reset_str)
            else:  # tier 3 — extreme
                body = t("notif.extreme", pct=f"{max_util:.0f}", reset=reset_str)

            notif.set_body(body)
            notif.set_priority(
                Gio.NotificationPriority.URGENT if new_tier >= 3
                else Gio.NotificationPriority.HIGH if new_tier == 2
                else Gio.NotificationPriority.NORMAL
            )
            self.send_notification("usage-alert", notif)
        except Exception as e:
            # Las notificaciones son "best effort"
            print(f"Warning: Failed to send notification: {e}", file=sys.stderr)

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
