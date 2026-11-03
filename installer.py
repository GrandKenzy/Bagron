"""Instalador y configurador de entorno para Bagron.

Instala Bagron en el directorio de usuario (por defecto: %USERPROFILE%/Bagron),
crea las carpetas de librerías/módulos, genera los lanzadores de CLI para el PATH
y permite invocar Bagron directamente desde cualquier terminal.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


# ============================================================================
# Constantes y rutas
# ============================================================================

DEFAULT_INSTALL_NAME = 'Bagron'
SUBDIRS_TO_COPY = ('core', 'tools', 'vendor', 'examples', 'docs', 'badge')
FILES_TO_COPY = ('main.py', 'vnma.toml', 'vnma.lock', 'README.md', 'LICENSE')
EMPTY_DIRS = ('libs', 'modules')


# ============================================================================
# Registro y PATH en Windows
# ============================================================================

def _add_to_windows_user_path(bin_path: Path) -> bool:
    """Añade bin_path al PATH de usuario en el registro de Windows si no está presente."""
    # NOTA: Solo aplica a plataformas Windows; en otros sistemas se reporta el path sugerido.
    if sys.platform != 'win32':
        return False

    import winreg
    import ctypes

    bin_str = str(bin_path.resolve())
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'Environment',
            0,
            winreg.KEY_READ | winreg.KEY_WRITE,
        )
    except OSError as error:
        print(f'Advertencia: no se pudo abrir la clave Environment del registro: {error}', file=sys.stderr)
        return False

    with key:
        try:
            current_path, path_type = winreg.QueryValueEx(key, 'Path')
        except FileNotFoundError:
            current_path = ''
            path_type = winreg.REG_EXPAND_SZ

        entries = [p.strip() for p in current_path.split(';') if p.strip()]
        normalized = [os.path.normcase(os.path.normpath(p)) for p in entries]
        bin_norm = os.path.normcase(os.path.normpath(bin_str))

        if bin_norm in normalized:
            return False

        entries.append(bin_str)
        new_path = ';'.join(entries)
        winreg.SetValueEx(key, 'Path', 0, path_type, new_path)

    # CUIDADO: Es necesario propagar WM_SETTINGCHANGE para que nuevas consolas detecten el cambio.
    try:
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        result = ctypes.c_long()
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            'Environment',
            SMTO_ABORTIFHUNG,
            5000,
            ctypes.byref(result),
        )
    except Exception:
        pass

    # Actualiza el entorno del proceso en ejecución
    current_proc_path = os.environ.get('PATH', '')
    if bin_str not in current_proc_path:
        os.environ['PATH'] = f"{bin_str};{current_proc_path}"

    return True


def _remove_from_windows_user_path(bin_path: Path) -> bool:
    """Remueve bin_path del PATH de usuario en el registro de Windows."""
    if sys.platform != 'win32':
        return False

    import winreg
    import ctypes

    bin_norm = os.path.normcase(os.path.normpath(str(bin_path.resolve())))
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'Environment',
            0,
            winreg.KEY_READ | winreg.KEY_WRITE,
        )
    except OSError:
        return False

    with key:
        try:
            current_path, path_type = winreg.QueryValueEx(key, 'Path')
        except FileNotFoundError:
            return False

        entries = [p.strip() for p in current_path.split(';') if p.strip()]
        filtered = [
            p for p in entries
            if os.path.normcase(os.path.normpath(p)) != bin_norm
        ]

        if len(filtered) == len(entries):
            return False

        new_path = ';'.join(filtered)
        winreg.SetValueEx(key, 'Path', 0, path_type, new_path)

    try:
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        result = ctypes.c_long()
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            'Environment',
            SMTO_ABORTIFHUNG,
            5000,
            ctypes.byref(result),
        )
    except Exception:
        pass

    return True


# ============================================================================
# Generación de lanzadores de comandos
# ============================================================================

def _create_launchers(bin_dir: Path) -> None:
    """Crea los scripts ejecutables Bagron.cmd y Bagron.ps1 en bin_dir."""
    bin_dir.mkdir(parents=True, exist_ok=True)

    # Script Batch / CMD para Windows
    cmd_content = (
        '@echo off\r\n'
        'setlocal\r\n'
        'set "BAGRON_CALLER_DIR=%CD%"\r\n'
        'set "BAGRON_HOME=%~dp0.."\r\n'
        'pushd "%BAGRON_HOME%"\r\n'
        'vnma run main.py %*\r\n'
        'set "EXIT_CODE=%ERRORLEVEL%"\r\n'
        'popd\r\n'
        'exit /b %EXIT_CODE%\r\n'
    )

    # Script PowerShell
    ps1_content = (
        '$callerDir = (Get-Location).Path\r\n'
        '$bagronHome = (Resolve-Path "$PSScriptRoot\\..").Path\r\n'
        '$env:BAGRON_CALLER_DIR = $callerDir\r\n'
        'Push-Location $bagronHome\r\n'
        'try {\r\n'
        '    vnma run main.py @args\r\n'
        '    $code = $LASTEXITCODE\r\n'
        '} finally {\r\n'
        '    Pop-Location\r\n'
        '    Remove-Item Env:BAGRON_CALLER_DIR -ErrorAction SilentlyContinue\r\n'
        '}\r\n'
        'exit $code\r\n'
    )

    # NOTA: Se generan variantes con mayúscula y minúscula para compatibilidad de invocación.
    for name in ('Bagron.cmd', 'bagron.cmd'):
        (bin_dir / name).write_text(cmd_content, encoding='utf-8')

    for name in ('Bagron.ps1', 'bagron.ps1'):
        (bin_dir / name).write_text(ps1_content, encoding='utf-8')


# ============================================================================
# Instalación y desinstalación
# ============================================================================

def install(target_dir: Path | None = None) -> int:
    """Instala Bagron en target_dir (por defecto %USERPROFILE%/Bagron)."""
    source_root = Path(__file__).resolve().parent

    if target_dir is None:
        target_dir = Path.home() / DEFAULT_INSTALL_NAME

    target_dir = target_dir.resolve()
    print(f'=== Instalador de Bagron 1.0.0 ===')
    print(f'Origen:  {source_root}')
    print(f'Destino: {target_dir}')

    is_in_place = (source_root == target_dir)

    target_dir.mkdir(parents=True, exist_ok=True)

    # Copia de contenido del proyecto
    if not is_in_place:
        print('\n[1/4] Copiando componentes del compilador...')
        ignore_patterns = shutil.ignore_patterns(
            '__pycache__',
            '*.pyc',
            '.git*',
            'build',
            'log',
            '.pytest_cache',
            '*.obj',
            '*.ll',
        )

        for subdir in SUBDIRS_TO_COPY:
            src_subdir = source_root / subdir
            if src_subdir.is_dir():
                dst_subdir = target_dir / subdir
                shutil.copytree(
                    src_subdir,
                    dst_subdir,
                    dirs_exist_ok=True,
                    ignore=ignore_patterns,
                )

        # NOTA: build/aot contiene la biblioteca nativa bagron_aot.dll requerida por el frontend FFI.
        src_aot = source_root / 'build' / 'aot'
        if src_aot.is_dir():
            dst_aot = target_dir / 'build' / 'aot'
            shutil.copytree(src_aot, dst_aot, dirs_exist_ok=True)

        for filename in FILES_TO_COPY:
            src_file = source_root / filename
            if src_file.is_file():
                shutil.copy2(src_file, target_dir / filename)
    else:
        print('\n[1/4] Instalación en el mismo directorio (omitiendo copia)...')

    # Creación de carpetas vacías para librerías y módulos
    print('[2/4] Creando carpetas base libs/ y modules/...')
    for empty_name in EMPTY_DIRS:
        empty_path = target_dir / empty_name
        empty_path.mkdir(parents=True, exist_ok=True)

    # Creación de lanzadores en bin/
    print('[3/4] Generando lanzadores CLI en bin/ (Bagron.cmd)...')
    bin_dir = target_dir / 'bin'
    _create_launchers(bin_dir)

    # Configuración de PATH
    print('[4/4] Configurando variables de entorno...')
    added_to_path = _add_to_windows_user_path(bin_dir)
    if added_to_path:
        print(f'  [OK] Ruta anadida al PATH de usuario: {bin_dir}')
    else:
        print(f'  [OK] La ruta ya se encontraba en el PATH: {bin_dir}')

    # Verificación de vnma
    vnma_path = shutil.which('vnma')
    if not vnma_path:
        print(
            '\n# CUIDADO: "vnma" no se detecto en el PATH actual.\n'
            'Bagron requiere vnma para resolver el entorno de dependencias.\n'
            'Asegurate de que la CLI de vnma este instalada y en el PATH.',
            file=sys.stderr,
        )
    else:
        print(f'  [OK] vnma detectado en: {vnma_path}')

    print('\n¡Instalación completada con éxito!')
    print('Ahora puedes abrir una nueva terminal y ejecutar:')
    print('  Bagron "ruta/a/archivo.bg" -o programa.exe')
    print('  Bagron --execute "ruta/a/archivo.bg" -o programa.exe\n')
    return 0


def uninstall(target_dir: Path | None = None) -> int:
    """Desinstala Bagron y retira su directorio bin del PATH."""
    if target_dir is None:
        target_dir = Path.home() / DEFAULT_INSTALL_NAME

    target_dir = target_dir.resolve()
    bin_dir = target_dir / 'bin'

    print(f'=== Desinstalador de Bagron ===')
    print(f'Objetivo: {target_dir}')

    if bin_dir.exists():
        removed = _remove_from_windows_user_path(bin_dir)
        if removed:
            print(f'  [OK] Ruta retirada del PATH: {bin_dir}')
        else:
            print(f'  - La ruta no estaba presente en el PATH: {bin_dir}')

    if target_dir.exists():
        try:
            shutil.rmtree(target_dir)
            print(f'  [OK] Carpeta eliminada: {target_dir}')
        except OSError as error:
            print(f'  Error al eliminar {target_dir}: {error}', file=sys.stderr)
            return 1

    print('Desinstalación finalizada.')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Instalador de Bagron')
    parser.add_argument(
        '--target',
        type=Path,
        default=None,
        help='Directorio de destino (por defecto: %%USERPROFILE%%/Bagron)',
    )
    parser.add_argument(
        '--uninstall',
        action='store_true',
        help='Desinstala Bagron y elimina la ruta del PATH',
    )
    args = parser.parse_args()

    if args.uninstall:
        return uninstall(args.target)
    return install(args.target)


if __name__ == '__main__':
    sys.exit(main())
