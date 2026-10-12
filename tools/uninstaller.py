"""Desinstalador independiente de EGL.

Puede ser invocado directamente por el usuario (ej: `egl-uninstall`),
desde 'Agregar o quitar programas' de Windows, o por el instalador.
Para evitar errores de bloqueo de archivos en Windows (WinError 32 / WinError 5),
se relanza automáticamente como proceso desacoplado desde una carpeta temporal en %TEMP%
esperando a que el proceso invocador termine antes de purgar los archivos.
"""
from __future__ import annotations

import ctypes
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

APP_NAME = "EGL"
REGISTRY_ENV_KEY = r"Environment"
REGISTRY_PATH_VALUE = "Path"
REG_UNINSTALL_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"


def log(msg: str) -> None:
    print(f"[Uninstaller] {msg}", flush=True)


def _broadcast_change() -> None:
    try:
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        result = ctypes.c_ulong()
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, REGISTRY_ENV_KEY, SMTO_ABORTIFHUNG, 3000, ctypes.byref(result)
        )
    except Exception:
        pass


def remove_from_user_path(bin_dir: Path) -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    bin_str = str(bin_dir.resolve()).lower()
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_ENV_KEY, 0, winreg.KEY_ALL_ACCESS)
        try:
            try:
                curr, _ = winreg.QueryValueEx(key, REGISTRY_PATH_VALUE)
            except FileNotFoundError:
                curr = ""
            paths = [p.strip() for p in curr.split(";") if p.strip()]
            new_paths = [p for p in paths if p.lower() != bin_str]
            winreg.SetValueEx(key, REGISTRY_PATH_VALUE, 0, winreg.REG_EXPAND_SZ, ";".join(new_paths))
        finally:
            winreg.CloseKey(key)
        _broadcast_change()
        log(f"Ruta removida del PATH del usuario: '{bin_str}'")
        return True
    except Exception as e:
        log(f"Error al remover del PATH: {e}")
        return False


def remove_registry_uninstall() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_UNINSTALL_KEY)
        log("Registro de Windows eliminado.")
        return True
    except FileNotFoundError:
        return True
    except Exception as e:
        log(f"Error al limpiar clave de registro: {e}")
        return False


def _handle_remove_readonly(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def force_remove_tree(path: Path) -> bool:
    if not path.exists():
        return True
    for attempt in range(5):
        try:
            shutil.rmtree(path, onerror=_handle_remove_readonly)
            if not path.exists():
                return True
        except Exception:
            pass
        time.sleep(0.5)

    if path.exists() and sys.platform == "win32":
        # Fallback usando comando nativo de Windows si algún subárbol persiste
        try:
            subprocess.run(["cmd.exe", "/c", "rmdir", "/s", "/q", str(path)], capture_output=True, timeout=5)
        except Exception:
            pass
    return not path.exists()


def wait_for_pid(pid: int, timeout_secs: float = 6.0) -> None:
    """Espera a que un proceso termine por su PID (Windows)."""
    if pid <= 0 or sys.platform != "win32":
        time.sleep(1.0)
        return
    SYNCHRONIZE = 0x00100000
    h_proc = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if h_proc:
        try:
            timeout_ms = int(timeout_secs * 1000)
            ctypes.windll.kernel32.WaitForSingleObject(h_proc, timeout_ms)
        finally:
            ctypes.windll.kernel32.CloseHandle(h_proc)
    time.sleep(0.5)


def get_default_install_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / "Programs" / APP_NAME


def run_uninstallation(target_dir: Path) -> bool:
    log(f"Iniciando desinstalación de {APP_NAME} de: '{target_dir}'...")

    # 1. Remover PATH
    bin_dir = target_dir / "bin"
    remove_from_user_path(bin_dir)

    # 2. Remover entrada en Agregar o quitar programas
    remove_registry_uninstall()

    # 3. Eliminar directorio destino
    if target_dir.exists():
        log("Eliminando archivos y carpetas...")
        ok = force_remove_tree(target_dir)
        if not ok:
            log(f"Advertencia: No se pudieron eliminar todos los archivos de '{target_dir}'.")
            return False

    log(f"¡{APP_NAME} se ha desinstalado completamente de tu sistema!")
    return True


def main() -> int:
    args = sys.argv[1:]
    target_dir = None
    is_temp_worker = False
    wait_pid = 0

    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--target", "-t") and i + 1 < len(args):
            target_dir = Path(args[i + 1]).resolve()
            i += 2
        elif a == "--worker":
            is_temp_worker = True
            i += 1
        elif a == "--wait-pid" and i + 1 < len(args):
            try:
                wait_pid = int(args[i + 1])
            except ValueError:
                wait_pid = 0
            i += 2
        elif a in ("-h", "--help"):
            print("Desinstalador de EGL")
            print("Uso:")
            print("  egl-uninstall.cmd [opciones]")
            print("  python uninstaller.py [opciones]")
            print("\nOpciones:")
            print("  --target, -t    Ruta específica de instalación.")
            return 0
        else:
            i += 1

    if target_dir is None:
        # Si se invoca desde el script dentro de EGL (ej: bin/uninstaller.py)
        here = Path(__file__).resolve()
        candidate = here.parent.parent
        if here.parent.name == "bin" and (candidate / "egl.py").is_file():
            target_dir = candidate
        elif here.parent.name == "bin" and candidate.name.lower() == APP_NAME.lower():
            target_dir = candidate
        else:
            target_dir = get_default_install_dir()

    target_dir = Path(target_dir).resolve()

    # Si nos estamos ejecutando dentro de target_dir, copiarnos a TEMP y relanzarnos desacoplados
    here = Path(__file__).resolve()
    try:
        in_target = target_dir in here.parents or here == target_dir
    except Exception:
        in_target = False

    if in_target and not is_temp_worker:
        temp_dir = Path(tempfile.mkdtemp(prefix="egl_uninst_"))
        temp_script = temp_dir / "uninstaller.py"
        shutil.copy2(here, temp_script)

        py_bin = shutil.which("python") or sys.executable
        my_pid = os.getpid()
        cmd = [
            py_bin,
            str(temp_script),
            "--worker",
            "--wait-pid",
            str(my_pid),
            "--target",
            str(target_dir),
        ]
        log("Relanzando desinstalador en proceso temporal para evitar bloqueo de archivos...")

        # Lanzar proceso desacoplado para permitir que este proceso termine inmediatamente
        if sys.platform == "win32":
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            subprocess.Popen(cmd, creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP, close_fds=True)
        else:
            subprocess.Popen(cmd, close_fds=True)
        return 0

    if is_temp_worker and wait_pid > 0:
        wait_for_pid(wait_pid)

    success = run_uninstallation(target_dir)

    if is_temp_worker:
        # Limpiar carpeta temporal del worker
        try:
            shutil.rmtree(here.parent, ignore_errors=True)
        except Exception:
            pass

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
