"""Gestión de instalación/desinstalación del autostart y dependencias."""

import shutil
import subprocess
import sys
from pathlib import Path

from .config import ASSETS_DIR, _log

AUTOSTART_DIR = Path.home() / ".config" / "autostart"
DESKTOP_FILENAME = "com.claudeusage.watcher.desktop"
DESKTOP_PATH = AUTOSTART_DIR / DESKTOP_FILENAME

# Nombres de .desktop files antiguos que debemos limpiar
_LEGACY_DESKTOP_FILES = [
    "claude-usage-indicator.desktop",
    "claude-usage-watcher.desktop",
]

REQUIRED_GI_MODULES = {
    "Gtk": ("3.0", "gir1.2-gtk-3.0"),
    "Notify": ("0.7", "gir1.2-notify-0.7"),
}

REQUIRED_PACKAGES = {
    "gi": "python3-gi",
    "cairo": "python3-cairo",
}


def _find_executable() -> str:
    """Encuentra la ruta absoluta al comando claude-usage-watcher instalado."""
    exe = shutil.which("claude-usage-watcher")
    if exe:
        return exe
    # Fallback: buscar en la ubicación típica de pip --user
    import sysconfig
    user_scripts = Path(sysconfig.get_path("scripts", "posix_user"))
    candidate = user_scripts / "claude-usage-watcher"
    if candidate.exists():
        return str(candidate)
    # Último recurso: usar python -m
    return f"{sys.executable} -m watcher.tray"


def _check_system_deps() -> list[str]:
    """Devuelve lista de paquetes apt faltantes."""
    missing = []
    for module, pkg in REQUIRED_PACKAGES.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(pkg)

    import gi
    for ns, (ver, pkg) in REQUIRED_GI_MODULES.items():
        try:
            gi.require_version(ns, ver)
        except ValueError:
            missing.append(pkg)

    return missing


def _remove_legacy_desktop_files():
    """Elimina archivos .desktop antiguos de autostart."""
    for name in _LEGACY_DESKTOP_FILES:
        old = AUTOSTART_DIR / name
        if old.exists():
            old.unlink()
            _log.info(f"Removed legacy desktop file: {old}")


def _generate_initial_icons():
    """Genera el icono inicial para que el .desktop tenga algo que mostrar."""
    from .icons import generate_icons
    generate_icons()


def _create_desktop_file():
    """Crea el archivo .desktop para autostart."""
    AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
    exec_path = _find_executable()
    icon_path = ASSETS_DIR / "icon_current.png"

    content = f"""[Desktop Entry]
Type=Application
Name=Claude Usage Watcher
Exec={exec_path} --autostart
Icon={icon_path}
Comment=Shows Claude API usage in the system tray
Categories=Utility;
StartupNotify=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
"""
    DESKTOP_PATH.write_text(content)
    _log.info(f"Autostart entry created: {DESKTOP_PATH}")


def install():
    """Instala el autostart: verifica deps, genera iconos, crea .desktop."""
    print("Claude Usage Watcher — Install")
    print()

    # 1. Verificar dependencias del sistema
    missing = _check_system_deps()
    if missing:
        pkgs = " ".join(missing)
        print(f"Missing system packages: {pkgs}")
        print(f"Installing with: sudo apt install -y {pkgs}")
        try:
            subprocess.check_call(["sudo", "apt", "install", "-y"] + missing)
        except subprocess.CalledProcessError:
            print(f"ERROR: Could not install dependencies. Run manually:")
            print(f"  sudo apt install -y {pkgs}")
            sys.exit(1)

    # 2. Generar iconos iniciales
    print("Generating initial icons...")
    _generate_initial_icons()

    # 3. Limpiar archivos .desktop antiguos
    _remove_legacy_desktop_files()

    # 4. Crear .desktop para autostart
    _create_desktop_file()

    exec_path = _find_executable()
    print()
    print(f"Autostart entry created: {DESKTOP_PATH}")
    print(f"  Exec: {exec_path} --autostart")
    print()
    print("To start now:  claude-usage-watcher &")
    print("It will auto-start on next login.")


def uninstall():
    """Elimina el autostart .desktop file."""
    removed = False
    # Eliminar el actual
    if DESKTOP_PATH.exists():
        DESKTOP_PATH.unlink()
        print(f"Removed: {DESKTOP_PATH}")
        removed = True

    # Eliminar cualquier legacy también
    for name in _LEGACY_DESKTOP_FILES:
        old = AUTOSTART_DIR / name
        if old.exists():
            old.unlink()
            print(f"Removed legacy: {old}")
            removed = True

    if removed:
        print("Autostart disabled. The app will no longer start on login.")
    else:
        print("No autostart entry found.")
