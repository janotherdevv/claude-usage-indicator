import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from .base import BaseWindow


class DesktopWindow(BaseWindow):
    """GTK-native popup with Cairo fuel-gauge dials. Stub — full impl in Task 9."""
    def __init__(self, auto_hide=True):
        super().__init__(auto_hide=auto_hide)
        lbl = Gtk.Label(label="Desktop theme (coming soon)")
        self.window.add(lbl)

    def update(self, usage_data=None, error=None, updated_at=None, stale=False, history=None):
        pass
