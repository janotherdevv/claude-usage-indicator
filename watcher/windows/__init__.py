from ..config import get_theme
from .obsidian import ObsidianWindow
from .classic import ClassicWindow
from .desktop import DesktopWindow


def UsageWindow(auto_hide=True):
    theme = get_theme()
    if theme == "classic":
        return ClassicWindow(auto_hide=auto_hide)
    if theme == "desktop":
        return DesktopWindow(auto_hide=auto_hide)
    return ObsidianWindow(auto_hide=auto_hide)
