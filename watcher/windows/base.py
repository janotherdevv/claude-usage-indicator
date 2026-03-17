import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

from ..theme import tier, utilization_color
from ..i18n import t


def _hex(rgb):
    return f"#{int(rgb[0]*255):02x}{int(rgb[1]*255):02x}{int(rgb[2]*255):02x}"


_current_screen_provider = None


def _set_screen_provider(provider):
    """Swap the active GTK screen-level CSS provider, removing the previous one."""
    global _current_screen_provider
    screen = Gdk.Screen.get_default()
    if _current_screen_provider is not None and _current_screen_provider is not provider:
        Gtk.StyleContext.remove_provider_for_screen(screen, _current_screen_provider)
    if _current_screen_provider is not provider:
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        _current_screen_provider = provider


def _clear_screen_provider():
    """Remove any active screen-level CSS provider (used by themes that rely on GTK defaults)."""
    global _current_screen_provider
    if _current_screen_provider is not None:
        Gtk.StyleContext.remove_provider_for_screen(
            Gdk.Screen.get_default(), _current_screen_provider
        )
        _current_screen_provider = None


def _status_markup(utilization, text_color="#F4F4F5"):
    if utilization >= 100:
        label = t("status.limit_label")
        desc  = t("status.limit_desc")
    else:
        tr = tier(utilization)
        if tr == 0:
            label = t("status.safe_label")
            desc  = t("status.safe_desc")
        elif tr == 1:
            label = t("status.warning_label")
            desc  = t("status.warning_desc")
        elif tr == 2:
            label = t("status.critical_label")
            desc  = t("status.critical_desc")
        else:
            label = t("status.extreme_label")
            desc  = t("status.extreme_desc")
    color = _hex(utilization_color(utilization))
    desc_fg = f' foreground="{text_color}"' if text_color else ""
    return (
        f'<span foreground="{color}" weight="bold" size="small">{label}</span>\n'
        f'<span size="medium"{desc_fg}>{desc}</span>'
    )


class BaseWindow:
    """Shared boilerplate for all popup window designs."""
    def __init__(self, auto_hide=True, border_width=20):
        self.window = Gtk.Window()
        screen = self.window.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.window.set_visual(visual)
        self._apply_theme(self.window)
        self.window.set_skip_taskbar_hint(True)
        self.window.set_skip_pager_hint(True)
        self.window.set_decorated(False)
        self.window.set_border_width(border_width)
        self.window.set_resizable(False)
        if auto_hide:
            self.window.connect("focus-out-event", lambda w, e: w.hide() or True)
        self.window.connect("delete-event", lambda w, e: w.hide() or True)

    def _apply_theme(self, window):
        pass

    def show(self):
        self.window.show_all()
        self.window.present()
