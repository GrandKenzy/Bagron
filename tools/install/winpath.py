"""Funciones para registrar y limpiar EGL en Windows (PATH y Programas y Características)."""
from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from tools import config
from tools.install.console import log

REG_UNINSTALL_ROOT = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
REG_UNINSTALL_KEY = rf"{REG_UNINSTALL_ROOT}\{config.APP_NAME}"


def _broadcast_environment_change() -> None:
    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x001A
    SMTO_ABORTIFHUNG = 0x0002
    result = ctypes.c_ulong()
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST,
        WM_SETTINGCHANGE,
        0,
        config.REGISTRY_ENV_KEY,
        SMTO_ABORTIFHUNG,
        config.WM_SETTINGCHANGE_TIMEOUT_MS,
        ctypes.byref(result),
    )


def _read_paths(key) -> list[str]:
    import winreg

    try:
        current, _ = winreg.QueryValueEx(key, config.REGISTRY_PATH_VALUE)
    except FileNotFoundError:
        current = ""
    return [p.strip() for p in current.split(";") if p.strip()]


def _write_paths(key, paths: list[str]) -> None:
    import winreg

    winreg.SetValueEx(key, config.REGISTRY_PATH_VALUE, 0, winreg.REG_EXPAND_SZ, ";".join(paths))


def add_to_user_path(bin_dir: Path) -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    bin_str = str(Path(bin_dir).resolve())
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, config.REGISTRY_ENV_KEY, 0, winreg.KEY_ALL_ACCESS)
        try:
            paths = _read_paths(key)
            if any(p.lower() == bin_str.lower() for p in paths):
                log(f"La ruta '{bin_str}' ya se encuentra registrada en el PATH del usuario.")
                return True
            paths.append(bin_str)
            _write_paths(key, paths)
        finally:
            winreg.CloseKey(key)
        _broadcast_environment_change()
        log(f"¡Directorio añadido exitosamente al PATH del usuario! ('{bin_str}')")
        return True
    except Exception as e:
        log(f"No se pudo actualizar el PATH del registro: {e}", tag="Installer Error")
        return False


def remove_from_user_path(bin_dir: Path) -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    bin_str = str(Path(bin_dir).resolve()).lower()
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, config.REGISTRY_ENV_KEY, 0, winreg.KEY_ALL_ACCESS)
        try:
            paths = [p for p in _read_paths(key) if p.lower() != bin_str]
            _write_paths(key, paths)
        finally:
            winreg.CloseKey(key)
        _broadcast_environment_change()
        log("Ruta removida del PATH del usuario.")
        return True
    except Exception as e:
        log(f"No se pudo remover del PATH: {e}", tag="Installer Error")
        return False


def register_windows_uninstaller(install_dir: Path, uninstaller_cmd: Path, version: str = "0.2.0") -> bool:
    """Registra la entrada en 'Agregar o quitar programas' de Windows (HKCU)."""
    if sys.platform != "win32":
        return False
    import winreg

    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_UNINSTALL_KEY)
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, f"{config.APP_NAME} Compiler")
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, version)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "GrandKenzy")
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(install_dir.resolve()))
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{uninstaller_cmd.resolve()}"')
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(key)
        log("Registro de desinstalador en Windows configurado.")
        return True
    except Exception as e:
        log(f"No se pudo registrar en Agregar o quitar programas: {e}", tag="Installer Warning")
        return False


def unregister_windows_uninstaller() -> bool:
    """Elimina la entrada en 'Agregar o quitar programas' de Windows."""
    if sys.platform != "win32":
        return False
    import winreg

    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_UNINSTALL_KEY)
        log("Entrada en Agregar o quitar programas eliminada.")
        return True
    except FileNotFoundError:
        return True
    except Exception as e:
        log(f"No se pudo eliminar entrada de desinstalador: {e}", tag="Installer Warning")
        return False
