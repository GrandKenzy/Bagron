"""Instalador y configurador de entorno para Bagron.

Descarga o actualiza Bagron desde un release de GitHub (o sincroniza
localmente), configura las dependencias en vnma.toml con Gram remoto, extrae
un runtime Python portable, resuelve el entorno vendor mediante vnma aislado,
crea carpetas base y registra la CLI en el PATH de usuario.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
from pathlib import Path, PurePath
from pathlib import PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from core.version import BAGRON_VERSION
from tools.deduplicate_portable_python import restore_aliases, verify_manifest


DEFAULT_INSTALL_NAME = 'Bagron'
BAGRON_REPO_URL = 'https://github.com/GrandKenzy/Bagron.git'
BAGRON_ZIP_URL = f'https://github.com/GrandKenzy/Bagron/archive/refs/tags/{BAGRON_VERSION}.zip'
GITHUB_LATEST_RELEASE_URL = 'https://api.github.com/repos/GrandKenzy/Bagron/releases/latest'
GRAM_REPO_URL = 'https://github.com/GrandKenzy/Gram.git'
MIN_PYTHON_VERSION = (3, 14)
PORTABLE_PYTHON_BUNDLE_NAME = 'portable-python'
LOCAL_RUNTIME_NAME = '.runtime'

SUBDIRS_TO_COPY = (
    'core',
    'tools',
    'examples',
    'docs',
    'badge',
    'changelog',
)
FILES_TO_COPY = (
    'installer.py',
    'README.md',
    'LICENSE',
    'install.sh',
)
EMPTY_DIRS = ('libs',)
_PREBUILT_MANAGED_PATHS = (
    'core',
    'tools',
    'vendor',
    '.runtime',
    'build/aot',
    'examples',
    'docs',
    'badge',
    'changelog',
    'bin',
    'main.py',
    'installer.py',
    'README.md',
    'LICENSE',
    'install.sh',
    'vnma.toml',
    'bagron-prebuilt.json',
)
_LEGACY_INSTALL_PATHS = ('modules', 'vnma.lock')
_MAX_RELEASE_METADATA_BYTES = 4 * 1024 * 1024
_MAX_RELEASE_ASSET_BYTES = 512 * 1024 * 1024
_MAX_SOURCE_ARCHIVE_BYTES = 256 * 1024 * 1024
_MAX_SOURCE_ARCHIVE_ENTRIES = 20_000
_MAX_SOURCE_ARCHIVE_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
_WINDOWS_RESERVED_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    *(f'COM{index}' for index in range(1, 10)),
    *(f'LPT{index}' for index in range(1, 10)),
}


def _validate_release_https_url(value: str, *, field: str) -> str:
    """Validate a release URL before allowing the installer to follow it."""
    if not isinstance(value, str) or not value or any(character.isspace() for character in value):
        raise ValueError(f'{field} debe ser una URL HTTPS absoluta.')
    parsed = urllib.parse.urlparse(value)
    try:
        hostname = parsed.hostname
        parsed.port
    except ValueError as error:
        raise ValueError(f'{field} contiene un puerto invalido.') from error
    if (
        parsed.scheme.lower() != 'https'
        or not parsed.netloc
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError(f'{field} debe ser una URL HTTPS absoluta.')
    return value


class _ReleaseRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Keep update downloads on HTTPS and do not leak request credentials."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_release_https_url(newurl, field='La redirección de GitHub')
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is None:
            return None
        old_host = urllib.parse.urlparse(req.full_url).netloc.lower()
        new_host = urllib.parse.urlparse(newurl).netloc.lower()
        if old_host != new_host:
            for header in ('Authorization', 'Cookie', 'Accept'):
                redirected.remove_header(header)
        return redirected


_RELEASE_OPENER = urllib.request.build_opener(_ReleaseRedirectHandler())


def _open_release_url(request: urllib.request.Request, *, timeout: int):
    """Open a release request through the HTTPS-only redirect policy."""
    return _RELEASE_OPENER.open(request, timeout=timeout)


def _read_release_limited(response, *, limit: int, context: str) -> bytes:
    """Read release metadata or an asset without unbounded memory growth."""
    headers = getattr(response, 'headers', None)
    content_length = headers.get('Content-Length') if hasattr(headers, 'get') else None
    if isinstance(content_length, (str, int)) and content_length:
        try:
            if int(content_length) > limit:
                raise OSError(f'{context} supera el límite de tamaño permitido.')
        except ValueError as error:
            raise OSError(f'{context} tiene un Content-Length inválido.') from error

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(min(1024 * 1024, limit - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise OSError(f'{context} supera el límite de tamaño permitido.')
        chunks.append(chunk)
    return b''.join(chunks)


def _stream_release_limited(response, output, *, limit: int, context: str) -> int:
    """Stream a release asset to disk while enforcing its size limit."""
    headers = getattr(response, 'headers', None)
    content_length = headers.get('Content-Length') if hasattr(headers, 'get') else None
    if isinstance(content_length, (str, int)) and content_length:
        try:
            if int(content_length) > limit:
                raise OSError(f'{context} supera el límite de tamaño permitido.')
        except ValueError as error:
            raise OSError(f'{context} tiene un Content-Length inválido.') from error

    total = 0
    while True:
        chunk = response.read(min(1024 * 1024, limit - total + 1))
        if not chunk:
            return total
        total += len(chunk)
        if total > limit:
            raise OSError(f'{context} supera el límite de tamaño permitido.')
        output.write(chunk)


def _safe_release_member(name: str) -> PurePosixPath:
    """Validate a GitHub source-archive member for all supported filesystems."""
    if not isinstance(name, str) or not name or '\x00' in name:
        raise OSError(f'La ruta del ZIP de fuentes no es válida: {name!r}')
    if '\\' in name or ':' in name or name.startswith('/'):
        raise OSError(f'La ruta del ZIP de fuentes escapa de su raíz: {name!r}')
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {'.', '..'} for part in path.parts):
        raise OSError(f'La ruta del ZIP de fuentes escapa de su raíz: {name!r}')
    canonical = path.as_posix()
    if name.endswith('/'):
        canonical += '/'
    if canonical != name:
        raise OSError(f'La ruta del ZIP de fuentes no es canónica: {name!r}')
    for part in path.parts:
        if part.rstrip(' .') != part:
            raise OSError(f'La ruta del ZIP contiene un nombre Windows inválido: {name!r}')
        if part.split('.', 1)[0].upper() in _WINDOWS_RESERVED_NAMES:
            raise OSError(f'La ruta del ZIP contiene un nombre reservado: {name!r}')
    return path


def _release_asset_magic() -> bytes:
    """Return the executable signature expected for the current release target."""
    if os.name == 'nt':
        return b'MZ'
    if sys.platform == 'linux':
        return b'\x7fELF'
    return b''


def _host_release_platform() -> str:
    """Return the platform for which this repository publishes a frozen installer."""
    if os.name == 'nt':
        return 'windows'
    if sys.platform == 'linux':
        return 'linux'
    raise RuntimeError(
        f'Bagron no publica todavía un instalador preconstruido para {sys.platform}; '
        'usa la instalación desde fuentes en este host.'
    )


def _runtime_python_path(runtime_dir: Path) -> Path:
    """Devuelve el intérprete Python del runtime según la plataforma actual."""
    if os.name == 'nt':
        if (runtime_dir / 'python.exe').is_file():
            return runtime_dir / 'python.exe'
        return runtime_dir / 'Scripts' / 'python.exe'
    return runtime_dir / 'bin' / 'python'


def _vnma_path(runtime_dir: Path) -> Path:
    """Devuelve el ejecutable vnma instalado en el runtime local."""
    if os.name == 'nt':
        if (runtime_dir / 'Scripts').is_dir():
            return runtime_dir / 'Scripts' / 'vnma.exe'
        return runtime_dir / 'vnma.exe'
    return runtime_dir / 'bin' / 'vnma'


def _bundled_python_dir() -> Path | None:
    """Devuelve el runtime que PyInstaller extrae junto al instalador."""
    if not getattr(sys, 'frozen', False):
        return None
    meipass = getattr(sys, '_MEIPASS', None)
    if not meipass:
        return None
    bundled_dir = Path(meipass) / PORTABLE_PYTHON_BUNDLE_NAME
    return bundled_dir if bundled_dir.is_dir() else None


def _find_system_python() -> list[str] | None:
    """Localiza Python 3.14+ para instalaciones ejecutadas desde el código fuente."""
    candidates: list[list[str]] = []
    if not getattr(sys, 'frozen', False):
        candidates.append([sys.executable])

    if os.name == 'nt':
        py_launcher = shutil.which('py')
        if py_launcher:
            candidates.append([py_launcher, f'-{MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}'])

    for name in (
        f'python{MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}',
        'python3',
        'python',
    ):
        resolved = shutil.which(name)
        if resolved:
            candidates.append([resolved])

    seen: set[tuple[str, ...]] = set()
    probe = (
        'import sys; '
        f'raise SystemExit(0 if sys.version_info >= {MIN_PYTHON_VERSION!r} else 1)'
    )
    for command in candidates:
        key = tuple(command)
        if key in seen:
            continue
        seen.add(key)
        try:
            result = subprocess.run(
                [*command, '-c', probe],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except OSError:
            continue
        if result.returncode == 0:
            return command
    return None


def _bootstrap_vnma(target_dir: Path) -> Path | None:
    """Prepara el runtime local y añade vnma sin modificar el sistema."""
    runtime_dir = target_dir / LOCAL_RUNTIME_NAME
    bundled_dir = _bundled_python_dir()

    if bundled_dir is not None:
        print(f'  [1/2] Extrayendo Python portable en {runtime_dir}...')
        try:
            shutil.copytree(bundled_dir, runtime_dir, dirs_exist_ok=True, symlinks=True)
        except OSError as error:
            print(f'Error: no se pudo extraer el Python portable: {error}', file=sys.stderr)
            return None
    else:
        # El instalador compilado debe incluir su propio Python portable.
        if getattr(sys, 'frozen', False):
            print(
                'Error: el instalador compilado no contiene su runtime Python portable.',
                file=sys.stderr,
            )
            return None
        python_command = _find_system_python()
        if python_command is None:
            print(
                f'Error: se necesita Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]} '
                'o superior para preparar las dependencias de Bagron.',
                file=sys.stderr,
            )
            return None
        print(f'  [1/2] Creando runtime local de desarrollo en {runtime_dir}...')
        try:
            result = subprocess.run(
                [*python_command, '-m', 'venv', '--clear', str(runtime_dir)],
                check=False,
            )
        except OSError as error:
            print(f'Error: no se pudo crear el runtime de Bagron: {error}', file=sys.stderr)
            return None
        if result.returncode != 0:
            print('Error: Python no pudo crear el runtime local de Bagron.', file=sys.stderr)
            return None

    runtime_python = _runtime_python_path(runtime_dir)
    vnma_bin = _vnma_path(runtime_dir)
    if not runtime_python.is_file():
        print('Error: el runtime local no contiene un ejecutable Python.', file=sys.stderr)
        return None

    runtime_probe = subprocess.run(
        [str(runtime_python), '--version'],
        capture_output=True,
        text=True,
        check=False,
    )
    if runtime_probe.returncode != 0:
        print(
            'Error: el runtime de Python de Bagron no se puede ejecutar. '
            f'{runtime_probe.stderr.strip()}',
            file=sys.stderr,
        )
        return None

    pip_probe = subprocess.run(
        [str(runtime_python), '-m', 'pip', '--version'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if pip_probe.returncode != 0:
        print('  [2/2] Habilitando pip dentro del entorno privado...')
        ensurepip = subprocess.run(
            [str(runtime_python), '-m', 'ensurepip', '--upgrade'],
            check=False,
        )
        if ensurepip.returncode != 0:
            print('Error: el runtime no contiene un pip utilizable.', file=sys.stderr)
            return None

        pip_probe = subprocess.run(
            [str(runtime_python), '-m', 'pip', '--version'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if pip_probe.returncode != 0:
            print(
                'Error: pip no quedó disponible dentro del runtime de Bagron.',
                file=sys.stderr,
            )
            return None

    if not vnma_bin.is_file():
        print('  [2/2] Instalando vnma dentro del entorno privado...')
        install = subprocess.run(
            [
                str(runtime_python),
                '-m',
                'pip',
                'install',
                '--upgrade',
                'vnma',
            ],
            check=False,
        )
        if install.returncode != 0 or not vnma_bin.is_file():
            print('Error: no se pudo instalar vnma en el runtime de Bagron.', file=sys.stderr)
            return None

    return vnma_bin.resolve()


def _add_to_windows_user_path(bin_path: Path) -> bool:
    """Añade bin_path al PATH de usuario en el registro de Windows si no está presente."""
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

    # Notifica el cambio para que las nuevas consolas recarguen el entorno.
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
        current_proc_path = os.environ.get('PATH', '')
        os.environ['PATH'] = ';'.join(
            p for p in current_proc_path.split(';')
            if p and os.path.normcase(os.path.normpath(p)) != bin_norm
        )
        return False

    with key:
        try:
            current_path, path_type = winreg.QueryValueEx(key, 'Path')
        except FileNotFoundError:
            current_proc_path = os.environ.get('PATH', '')
            os.environ['PATH'] = ';'.join(
                p for p in current_proc_path.split(';')
                if p and os.path.normcase(os.path.normpath(p)) != bin_norm
            )
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

    current_proc_path = os.environ.get('PATH', '')
    current_entries = [p for p in current_proc_path.split(';') if p]
    os.environ['PATH'] = ';'.join(
        p for p in current_entries
        if os.path.normcase(os.path.normpath(p)) != bin_norm
    )
    return True


def _add_to_posix_user_path(bin_path: Path) -> bool:
    """Instala lanzadores en ~/.local/bin sin editar perfiles de shell."""
    if os.name != 'posix':
        return False

    user_bin = Path.home() / '.local' / 'bin'
    try:
        user_bin.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        print(f'Advertencia: no se pudo crear {user_bin}: {error}', file=sys.stderr)
        return False

    _remove_legacy_posix_user_launcher(bin_path)

    for name in ('bagron',):
        launcher = bin_path / name
        link = user_bin / name
        if link.exists() or link.is_symlink():
            if link.is_symlink() and link.resolve() == launcher.resolve():
                continue
            print(
                f'Advertencia: no se reemplaza el archivo existente {link}.',
                file=sys.stderr,
            )
            return False
        try:
            link.symlink_to(launcher)
        except OSError as error:
            print(f'Advertencia: no se pudo crear el enlace {link}: {error}', file=sys.stderr)
            return False

    current_path = os.environ.get('PATH', '').split(os.pathsep)
    user_bin_text = str(user_bin)
    if user_bin_text not in current_path:
        os.environ['PATH'] = os.pathsep.join([user_bin_text, *current_path])
    return True


def _remove_from_posix_user_path(bin_path: Path) -> bool:
    """Retira solo los enlaces POSIX que apuntan a la instalación indicada."""
    if os.name != 'posix':
        return False

    user_bin = Path.home() / '.local' / 'bin'
    removed = _remove_legacy_posix_user_launcher(bin_path)
    for name in ('bagron',):
        link = user_bin / name
        if not link.is_symlink():
            continue
        try:
            if link.resolve() == (bin_path / name).resolve():
                link.unlink()
                removed = True
        except OSError:
            continue

    user_bin_norm = os.path.normcase(os.path.normpath(str(user_bin.resolve())))
    current_path = os.environ.get('PATH', '')
    os.environ['PATH'] = os.pathsep.join(
        entry for entry in current_path.split(os.pathsep)
        if entry and os.path.normcase(os.path.normpath(entry)) != user_bin_norm
    )
    return removed


def _remove_legacy_posix_user_launcher(bin_path: Path) -> bool:
    """Retira el alias POSIX ``Bagron`` heredado de instalaciones anteriores."""
    if os.name != 'posix':
        return False

    legacy_link = Path.home() / '.local' / 'bin' / 'Bagron'
    if not legacy_link.is_symlink():
        return False

    try:
        if legacy_link.resolve() != (bin_path / 'Bagron').resolve():
            return False
        legacy_link.unlink()
        return True
    except OSError:
        return False


def _create_launchers(bin_dir: Path) -> None:
    """Crea los lanzadores nativos para Windows o sistemas POSIX."""
    bin_dir.mkdir(parents=True, exist_ok=True)

    # Limpia alias antiguos solo dentro del directorio administrado.
    for legacy_name in ('Bagron', 'Bagron.cmd', 'Bagron.ps1'):
        legacy_launcher = bin_dir / legacy_name
        if legacy_launcher.is_file() or legacy_launcher.is_symlink():
            legacy_launcher.unlink()

    if os.name == 'posix':
        shell_content = '''#!/usr/bin/env bash
set -euo pipefail

launcher_path="${BASH_SOURCE[0]}"
while [[ -L "$launcher_path" ]]; do
    launcher_dir="$(CDPATH= cd -- "$(dirname -- "$launcher_path")" && pwd)"
    launcher_path="$(readlink "$launcher_path")"
    [[ "$launcher_path" = /* ]] || launcher_path="$launcher_dir/$launcher_path"
done
launcher_dir="$(CDPATH= cd -- "$(dirname -- "$launcher_path")" && pwd)"
bagron_home="$(CDPATH= cd -- "$launcher_dir/.." && pwd)"
python_bin="$bagron_home/.runtime/bin/python"
if [[ ! -x "$python_bin" ]]; then
    printf '%s\n' 'Error: falta el Python portable de Bagron; ejecuta el instalador de Bagron de nuevo.' >&2
    exit 1
fi
export PYTHONPATH="$bagron_home/vendor${PYTHONPATH:+:$PYTHONPATH}"
if [[ "${1:-}" == "--update" || "${1:-}" == "--uninstall" ]]; then
    maintenance_command="$1"
    exec "$python_bin" "$bagron_home/installer.py" "$maintenance_command" --target "$bagron_home"
fi
export BAGRON_CALLER_DIR="$PWD"
cd "$bagron_home"
exec "$python_bin" "$bagron_home/main.py" "$@"
'''
        for name in ('bagron',):
            launcher = bin_dir / name
            launcher.write_text(shell_content, encoding='utf-8')
            launcher.chmod(0o755)
        return

    cmd_content = (
        '@echo off\r\n'
        'setlocal\r\n'
        'set "BAGRON_CALLER_DIR=%CD%"\r\n'
        'set "BAGRON_HOME=%~dp0.."\r\n'
        'set "PYTHON=%BAGRON_HOME%\\.runtime\\python.exe"\r\n'
        'if not exist "%PYTHON%" set "PYTHON=%BAGRON_HOME%\\.runtime\\Scripts\\python.exe"\r\n'
        'if not exist "%PYTHON%" (echo Error: falta el Python portable de Bagron; ejecuta el instalador de Bagron de nuevo. 1>&2 & exit /b 1)\r\n'
        'set "PYTHONPATH=%BAGRON_HOME%\\vendor;%PYTHONPATH%"\r\n'
        'if /I "%~1"=="--update" "%PYTHON%" "%BAGRON_HOME%\\installer.py" --update --target "%BAGRON_HOME%"\r\n'
        'if /I "%~1"=="--update" exit /b %ERRORLEVEL%\r\n'
        'if /I "%~1"=="--uninstall" "%PYTHON%" "%BAGRON_HOME%\\installer.py" --uninstall --target "%BAGRON_HOME%"\r\n'
        'if /I "%~1"=="--uninstall" exit /b %ERRORLEVEL%\r\n'
        'pushd "%BAGRON_HOME%"\r\n'
        '"%PYTHON%" "%BAGRON_HOME%\\main.py" %*\r\n'
        'set "EXIT_CODE=%ERRORLEVEL%"\r\n'
        'popd\r\n'
        'exit /b %EXIT_CODE%\r\n'
    )

    ps1_content = (
        '$callerDir = (Get-Location).Path\r\n'
        '$bagronHome = (Resolve-Path "$PSScriptRoot\\..").Path\r\n'
        '$python = Join-Path $bagronHome ".runtime\\python.exe"\r\n'
        'if (-not (Test-Path -LiteralPath $python)) { $python = Join-Path $bagronHome ".runtime\\Scripts\\python.exe" }\r\n'
        'if (-not (Test-Path -LiteralPath $python)) { Write-Error "Falta el Python portable de Bagron; ejecuta el instalador de Bagron de nuevo."; exit 1 }\r\n'
        '$env:PYTHONPATH = "$(Join-Path $bagronHome \'vendor\');$env:PYTHONPATH"\r\n'
        'if ($args.Count -gt 0 -and ($args[0] -eq "--update" -or $args[0] -eq "--uninstall")) {\r\n'
        '    & $python (Join-Path $bagronHome "installer.py") $args[0] --target $bagronHome\r\n'
        '    exit $LASTEXITCODE\r\n'
        '}\r\n'
        '$env:BAGRON_CALLER_DIR = $callerDir\r\n'
        'Push-Location $bagronHome\r\n'
        'try {\r\n'
        '    & $python (Join-Path $bagronHome "main.py") @args\r\n'
        '    $code = $LASTEXITCODE\r\n'
        '} finally {\r\n'
        '    Pop-Location\r\n'
        '    Remove-Item Env:BAGRON_CALLER_DIR -ErrorAction SilentlyContinue\r\n'
        '}\r\n'
        'exit $code\r\n'
    )

    (bin_dir / 'bagron.cmd').write_text(cmd_content, encoding='utf-8')
    (bin_dir / 'bagron.ps1').write_text(ps1_content, encoding='utf-8')


def _extract_github_source_zip(data: bytes, target_dir: Path) -> None:
    """Validate and safely extract the tagged source archive into the target."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data), 'r')
    except (OSError, zipfile.BadZipFile) as error:
        raise OSError(f'El ZIP de fuentes no es válido: {error}') from error

    try:
        infos = archive.infolist()
        if not infos:
            raise OSError('El ZIP de fuentes está vacío.')
        if len(infos) > _MAX_SOURCE_ARCHIVE_ENTRIES:
            raise OSError('El ZIP de fuentes contiene demasiadas entradas.')

        root_names: set[str] = set()
        entries: list[tuple[zipfile.ZipInfo, PurePosixPath, bool]] = []
        seen: set[str] = set()
        file_entries: set[str] = set()
        directory_entries: set[str] = set()
        total_size = 0

        for info in infos:
            safe = _safe_release_member(info.filename)
            if not safe.parts:
                raise OSError('El ZIP de fuentes contiene una ruta vacía.')
            root_names.add(safe.parts[0].casefold())
            if stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF):
                raise OSError(f'El ZIP de fuentes contiene un enlace simbólico: {info.filename!r}')
            is_directory = info.is_dir() or info.filename.endswith('/')
            if len(safe.parts) == 1:
                if not is_directory:
                    raise OSError('La raíz del ZIP de fuentes debe ser un directorio.')
                continue

            relative = PurePosixPath(*safe.parts[1:])
            key = relative.as_posix().casefold()
            if key in seen:
                raise OSError(f'El ZIP de fuentes contiene entradas duplicadas: {info.filename!r}')
            for parent in relative.parents:
                parent_key = parent.as_posix().casefold()
                if parent_key != '.' and parent_key in file_entries:
                    raise OSError(
                        f'El ZIP de fuentes mezcla un archivo y una carpeta: {info.filename!r}'
                    )
            if is_directory:
                if key in file_entries:
                    raise OSError(
                        f'El ZIP de fuentes mezcla un archivo y una carpeta: {info.filename!r}'
                    )
                directory_entries.add(key)
            else:
                if info.flag_bits & 0x1:
                    raise OSError(f'El ZIP de fuentes contiene una entrada cifrada: {info.filename!r}')
                if info.file_size < 0 or info.compress_size < 0:
                    raise OSError(f'El ZIP de fuentes tiene un tamaño inválido: {info.filename!r}')
                total_size += info.file_size
                if total_size > _MAX_SOURCE_ARCHIVE_UNCOMPRESSED_BYTES:
                    raise OSError('El ZIP de fuentes supera el límite descomprimido permitido.')
                file_entries.add(key)
            seen.add(key)
            entries.append((info, relative, is_directory))

        if len(root_names) != 1:
            raise OSError('El ZIP de fuentes debe contener una única carpeta raíz.')
        expected_root = f'bagron-{BAGRON_VERSION}'.casefold()
        if root_names != {expected_root}:
            raise OSError('El ZIP de fuentes no corresponde a la versión solicitada.')

        target_dir.mkdir(parents=True, exist_ok=True)
        for info, relative, is_directory in entries:
            output = target_dir.joinpath(*relative.parts)
            _assert_managed_path_is_local(target_dir, output)
            if is_directory:
                if output.is_symlink() or (output.exists() and not output.is_dir()):
                    raise OSError(f'La ruta de extracción no es un directorio seguro: {output}')
                output.mkdir(parents=True, exist_ok=True)
                continue
            if output.is_symlink() or output.is_dir():
                raise OSError(f'La ruta de extracción no es un archivo seguro: {output}')
            output.parent.mkdir(parents=True, exist_ok=True)
            _assert_managed_path_is_local(target_dir, output)
            fd, temporary_name = tempfile.mkstemp(
                prefix=f'.{output.name}.', suffix='.download', dir=output.parent
            )
            temporary = Path(temporary_name)
            try:
                copied = 0
                with os.fdopen(fd, 'wb') as destination, archive.open(info, 'r') as source:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        copied += len(chunk)
                        if copied > info.file_size:
                            raise OSError(f'El ZIP de fuentes excede el tamaño declarado: {info.filename!r}')
                        destination.write(chunk)
                    if copied != info.file_size:
                        raise OSError(f'El ZIP de fuentes está truncado: {info.filename!r}')
                    destination.flush()
                    os.fsync(destination.fileno())
                os.replace(temporary, output)
            finally:
                temporary.unlink(missing_ok=True)
    finally:
        archive.close()


def _fetch_from_github(target_dir: Path) -> None:
    """Descarga o clona Bagron desde GitHub en target_dir."""
    git_bin = shutil.which('git')

    if git_bin:
        if (target_dir / '.git').is_dir():
            print(f'  [Git] Sincronizando release {BAGRON_VERSION} en {target_dir}...')
            fetch = subprocess.run(
                [
                    git_bin,
                    'fetch',
                    '--depth',
                    '1',
                    'origin',
                    f'refs/tags/{BAGRON_VERSION}:refs/tags/{BAGRON_VERSION}',
                ],
                cwd=str(target_dir),
            )
            if fetch.returncode == 0:
                checkout = subprocess.run(
                    [git_bin, 'checkout', '--detach', f'tags/{BAGRON_VERSION}'],
                    cwd=str(target_dir),
                )
                if checkout.returncode == 0:
                    return
            print('  [Git] Advertencia: no se pudo sincronizar el tag; usando ZIP...')

        if not any(target_dir.iterdir()) if target_dir.exists() else True:
            print(f'  [Git] Clonando {BAGRON_REPO_URL}...')
            clone = subprocess.run(
                [
                    git_bin,
                    'clone',
                    '--depth',
                    '1',
                    '--branch',
                    BAGRON_VERSION,
                    BAGRON_REPO_URL,
                    str(target_dir),
                ],
                check=False,
            )
            if clone.returncode == 0:
                return
            print('  [Git] Advertencia: no se pudo clonar el tag; usando ZIP...')

    # Descarga directa mediante ZIP (cuando git no está disponible o la carpeta no está vacía)
    print(f'  [HTTP] Descargando archivo ZIP desde {BAGRON_ZIP_URL}...')
    try:
        request = urllib.request.Request(
            _validate_release_https_url(BAGRON_ZIP_URL, field='La URL de fuentes de GitHub'),
            headers={'Accept': 'application/zip', 'User-Agent': 'Bagron-installer'},
        )
        with _open_release_url(request, timeout=120) as response:
            zip_bytes = _read_release_limited(
                response,
                limit=_MAX_SOURCE_ARCHIVE_BYTES,
                context='El ZIP de fuentes descargado',
            )
        print('  [HTTP] Extrayendo archivos del release...')
        _extract_github_source_zip(zip_bytes, target_dir)
    except Exception as error:
        print(f'Error al descargar desde GitHub: {error}', file=sys.stderr)
        raise


def _release_version_tuple(version: str) -> tuple[int, ...]:
    """Valida una versión semver simple usada por los tags de Bagron."""
    normalized = version.strip()
    if normalized.startswith('v'):
        normalized = normalized[1:]
    parts = normalized.split('.')
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise ValueError(f'La release de GitHub tiene una versión inválida: {version!r}')
    return tuple(int(part) for part in parts)


def _release_asset_name(version: str) -> str:
    """Devuelve el nombre del instalador publicado para el sistema actual."""
    release_platform = _host_release_platform()
    if release_platform == 'windows':
        machine = platform.machine().lower()
        if machine not in {'amd64', 'x86_64'}:
            raise RuntimeError(
                f'No hay un instalador Windows publicado para la arquitectura {machine or "desconocida"}. '
                'Instala Bagron desde fuentes o publica un artefacto para ese target.'
            )
        return f'Bagron-{version}-Setup.exe'
    if release_platform == 'linux':
        machine = platform.machine().lower()
        if machine not in {'x86_64', 'amd64'}:
            raise RuntimeError(
                f'No hay un instalador Linux publicado para la arquitectura {machine or "desconocida"}. '
                'Instala Bagron desde fuentes o publica un artefacto para ese target.'
            )
        return f'Bagron-{version}-linux-x86_64'
    raise AssertionError(f'Unsupported Bagron release platform: {release_platform}')


def _latest_release() -> tuple[str, str]:
    """Consulta la release estable más reciente y devuelve tag y asset HTTPS."""
    api_url = _validate_release_https_url(
        GITHUB_LATEST_RELEASE_URL,
        field='La API de releases de GitHub',
    )
    request = urllib.request.Request(
        api_url,
        headers={
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'Bagron-installer',
        },
    )
    with _open_release_url(request, timeout=30) as response:
        metadata = json.loads(
            _read_release_limited(
                response,
                limit=_MAX_RELEASE_METADATA_BYTES,
                context='La metadata de releases de GitHub',
            ).decode('utf-8')
        )

    tag = metadata.get('tag_name')
    if not isinstance(tag, str):
        raise ValueError('La respuesta de GitHub no contiene tag_name.')
    _release_version_tuple(tag)

    expected_name = _release_asset_name(tag.lstrip('v'))
    for asset in metadata.get('assets', ()):
        if not isinstance(asset, dict) or asset.get('name') != expected_name:
            continue
        download_url = asset.get('browser_download_url')
        if not isinstance(download_url, str) or not download_url.startswith('https://'):
            raise ValueError('La release no contiene una URL HTTPS válida para el instalador.')
        return tag.lstrip('v'), download_url
    raise FileNotFoundError(f'La release {tag} no contiene el asset {expected_name}.')


def _download_release_asset(url: str, destination: Path) -> None:
    """Descarga un instalador a un archivo temporal sin mantenerlo en memoria."""
    url = _validate_release_https_url(url, field='La URL del instalador')
    request = urllib.request.Request(
        url,
        headers={'Accept': 'application/octet-stream', 'User-Agent': 'Bagron-installer'},
    )
    with _open_release_url(request, timeout=120) as response, destination.open('wb') as output:
        _stream_release_limited(
            response,
            output,
            limit=_MAX_RELEASE_ASSET_BYTES,
            context='El instalador descargado',
        )
        output.flush()
        os.fsync(output.fileno())
    if not destination.is_file() or destination.stat().st_size == 0:
        raise OSError('GitHub devolvió un instalador vacío.')
    expected_magic = _release_asset_magic()
    if expected_magic:
        with destination.open('rb') as input_file:
            actual_magic = input_file.read(len(expected_magic))
        if actual_magic != expected_magic:
            raise OSError('GitHub devolvió un archivo que no es un instalador ejecutable válido.')


def _running_from_installation(target_dir: Path) -> bool:
    """Indica si el proceso actual mantiene abierto el runtime que se actualizará."""
    try:
        Path(sys.executable).resolve().relative_to(target_dir.resolve())
    except ValueError:
        return False
    return True


def _resolve_local_target(target_dir: Path) -> Path:
    """Resolve an installation path without following a user-controlled link."""
    # Preserve an already materialized path class. Tests and callers may
    # simulate another host through ``os.name`` without changing the actual
    # filesystem, and rebuilding a POSIX path as WindowsPath would fail there.
    raw_target = (
        target_dir.expanduser()
        if isinstance(target_dir, PurePath)
        else Path(target_dir).expanduser()
    )
    for candidate in (raw_target, *raw_target.parents):
        if candidate.is_symlink():
            raise OSError(f'La ruta de instalación contiene un enlace simbólico: {candidate}')
    return raw_target.resolve()


def _windows_no_window_flags() -> int:
    """Return the Windows flag that suppresses helper consoles.

    ``CREATE_NO_WINDOW`` and ``DETACHED_PROCESS`` are mutually exclusive for
    console children.  Combining them was the reason the polling ``find.exe``
    process opened a visible console during the 1.1.5 update.
    """
    if os.name != 'nt':
        return 0
    return getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def _schedule_windows_update(installer_path: Path, target_dir: Path) -> bool:
    """Programa la actualización después de cerrar el Python portable actual."""
    if os.name != 'nt':
        return False

    script_path = installer_path.with_suffix('.cmd')
    try:
        script_path.write_text(
            '@echo off\r\n'
            'setlocal\r\n'
            'set "INSTALLER=%~1"\r\n'
            'set "TARGET=%~2"\r\n'
            'set "PARENT_PID=%~3"\r\n'
            ':wait_parent\r\n'
            'for /f "tokens=2 delims=," %%P in (\'\"%SystemRoot%\\System32\\tasklist.exe\" /FI "PID eq %PARENT_PID%" /FO CSV /NH 2^>nul\') do (\r\n'
            '  if "%%~P"=="%PARENT_PID%" (\r\n'
            '    "%SystemRoot%\\System32\\ping.exe" 127.0.0.1 -n 2 >nul\r\n'
            '    goto wait_parent\r\n'
            '  )\r\n'
            ')\r\n'
            'if not exist "%INSTALLER%" exit /b 2\r\n'
            '"%INSTALLER%" --target "%TARGET%"\r\n'
            'set "EXIT_CODE=%ERRORLEVEL%"\r\n'
            'del /F /Q "%INSTALLER%" >nul 2>&1\r\n'
            'del /F /Q "%~f0" >nul 2>&1\r\n'
            'rmdir /Q "%~dp0" >nul 2>&1\r\n'
            'exit /b %EXIT_CODE%\r\n',
            encoding='utf-8',
        )
        comspec = os.environ.get('ComSpec', 'cmd.exe')
        flags = _windows_no_window_flags()
        subprocess.Popen(
            [comspec, '/D', '/C', str(script_path), str(installer_path), str(target_dir), str(os.getpid())],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            cwd=str(script_path.parent),
            creationflags=flags,
        )
        return True
    except OSError:
        script_path.unlink(missing_ok=True)
        return False


def _schedule_posix_update(installer_path: Path, target_dir: Path) -> bool:
    """Schedule a self-update without keeping the installed runtime open."""
    if os.name != 'posix':
        return False

    shell = shutil.which('sh')
    if not shell:
        return False

    script_path = installer_path.with_suffix('.sh')
    try:
        script_path.write_text(
            '#!/bin/sh\n'
            'set -u\n'
            'installer=$1\n'
            'target=$2\n'
            'parent_pid=$3\n'
            'while kill -0 "$parent_pid" 2>/dev/null; do\n'
            '    sleep 1\n'
            'done\n'
            '"$installer" --target "$target"\n'
            'exit_code=$?\n'
            'rm -f "$installer" "$0"\n'
            'rmdir "$(dirname "$0")" 2>/dev/null || true\n'
            'exit "$exit_code"\n',
            encoding='utf-8',
        )
        script_path.chmod(0o700)
        subprocess.Popen(
            [shell, str(script_path), str(installer_path), str(target_dir), str(os.getpid())],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
            cwd=str(script_path.parent),
        )
        return True
    except OSError:
        script_path.unlink(missing_ok=True)
        return False


def _schedule_self_update(installer_path: Path, target_dir: Path) -> bool:
    """Select the native deferred-update helper for the current host."""
    if os.name == 'nt':
        return _schedule_windows_update(installer_path, target_dir)
    if os.name == 'posix':
        return _schedule_posix_update(installer_path, target_dir)
    return False


_INSTALLED_VERSION_RE = re.compile(r"^BAGRON_VERSION\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)


def _installed_version(target_dir: Path) -> str | None:
    """Lee la versión instalada sin importar módulos desde el runtime objetivo."""
    version_file = target_dir / 'core' / 'version.py'
    try:
        match = _INSTALLED_VERSION_RE.search(version_file.read_text(encoding='utf-8'))
    except OSError:
        return None
    return match.group(1) if match else None


def update(target_dir: Path | None = None) -> int:
    """Actualiza la instalación al último asset estable publicado en GitHub."""
    if target_dir is None:
        target_dir = Path.home() / DEFAULT_INSTALL_NAME
    try:
        target_dir = _resolve_local_target(target_dir)
    except OSError as error:
        print(f'Error: la ruta de instalación no es segura: {error}', file=sys.stderr)
        return 1
    if not target_dir.is_dir():
        print(f'Error: no existe una instalación de Bagron en {target_dir}.', file=sys.stderr)
        return 1

    print('=== Actualizador de Bagron ===')
    print(f'Objetivo: {target_dir}')
    try:
        latest_version, asset_url = _latest_release()
        latest_tuple = _release_version_tuple(latest_version)
        current_version = _installed_version(target_dir) or BAGRON_VERSION
        current_tuple = _release_version_tuple(current_version)
    except (OSError, RuntimeError, ValueError, urllib.error.URLError, json.JSONDecodeError) as error:
        print(f'Error: no se pudo consultar la última release de GitHub: {error}', file=sys.stderr)
        return 1

    print(f'Versión instalada: {current_version}')
    print(f'Última release estable: {latest_version}')
    if latest_tuple <= current_tuple:
        print('Bagron ya está actualizado.')
        return 0

    asset_name = _release_asset_name(latest_version)
    # Preserve the target path flavour when tests simulate another platform.
    temporary_dir = type(target_dir)(tempfile.mkdtemp(prefix='bagron-update-'))
    deferred = False
    try:
        installer_path = temporary_dir / asset_name
        print(f'Descargando {asset_name}...')
        _download_release_asset(asset_url, installer_path)
        if os.name != 'nt':
            installer_path.chmod(installer_path.stat().st_mode | 0o111)
        if _running_from_installation(target_dir):
            deferred = _schedule_self_update(installer_path, target_dir)
            if not deferred:
                print(
                    'Error: este sistema no pudo programar la actualización después de cerrar Bagron.',
                    file=sys.stderr,
                )
                return 1
            print('La actualización continuará al cerrar el proceso actual de Bagron.')
            return 0

        result = subprocess.run(
            [str(installer_path), '--target', str(target_dir)],
            check=False,
        )
        if result.returncode != 0:
            print('Error: el instalador de la nueva release terminó con error.', file=sys.stderr)
            return result.returncode or 1
    except (OSError, subprocess.SubprocessError, urllib.error.URLError) as error:
        print(f'Error: no se pudo descargar o ejecutar la actualización: {error}', file=sys.stderr)
        return 1
    finally:
        if not deferred:
            shutil.rmtree(temporary_dir, ignore_errors=True)

    print(f'Actualización a Bagron {latest_version} completada.')
    return 0


def _configure_vnma_toml(target_dir: Path) -> None:
    """Configura vnma.toml para apuntar a la dependencia remota de Gram."""
    vnma_toml_content = (
        '[project]\n'
        'name = "Bagron"\n'
        f'version = "{BAGRON_VERSION}"\n\n'
        '[dependencies]\n'
        f'gram = {{ git = "{GRAM_REPO_URL}", branch = "main" }}\n'
        'llvmlite = "==0.50.0"\n\n'
        '[dev-dependencies]\n\n'
        '[tool.vnma]\n'
        'vendor_dir = "vendor"\n'
        'ide_integration = ["vscode", "pycharm"]\n'
    )
    (target_dir / 'vnma.toml').write_text(vnma_toml_content, encoding='utf-8')
    stale_lock = target_dir / 'vnma.lock'
    if stale_lock.exists():
        # No reutiliza locks que apunten a un checkout editable de Gram.
        stale_lock.unlink()


def _aot_library_names() -> tuple[str, ...]:
    """Devuelve los nombres de biblioteca AOT esperados en la plataforma actual."""
    if sys.platform == 'win32':
        return ('bagron_aot.dll',)
    if sys.platform == 'darwin':
        return ('bagron_aot.dylib', 'libbagron_aot.dylib')
    return ('libbagron_aot.so', 'bagron_aot.so')


def _has_aot_parser(target_dir: Path) -> bool:
    """Comprueba que la reconstrucción AOT produjo la biblioteca y el manifiesto."""
    output_dir = target_dir / 'build' / 'aot'
    return (
        any((output_dir / name).is_file() for name in _aot_library_names())
        and (output_dir / 'gram_parser_manifest.json').is_file()
    )


def _build_aot_parser(target_dir: Path, vnma_bin: Path | None) -> bool:
    """Reconstruye la biblioteca FFI de Gram para la plataforma actual."""
    if not vnma_bin:
        print(
            '  [CUIDADO] No se puede generar el parser AOT porque falta vnma.',
            file=sys.stderr,
        )
        return False

    git_bin = shutil.which('git')
    if not git_bin:
        print(
            '  [CUIDADO] No se puede generar el parser AOT porque falta git.',
            file=sys.stderr,
        )
        return False

    print('\n[5/7] Construyendo la biblioteca AOT/FFI de Gram...')
    output_dir = target_dir / 'build' / 'aot'
    try:
        # El AOT y su manifiesto deben proceder de la misma reconstrucción.
        # Limpiar solo esta salida evita reutilizar pares incompatibles de Gram.
        if output_dir.exists():
            shutil.rmtree(output_dir)

        with tempfile.TemporaryDirectory(prefix='bagron-gram-') as temporary:
            gram_dir = Path(temporary) / 'Gram'
            clone = subprocess.run(
                [git_bin, 'clone', '--depth', '1', '--branch', 'main', GRAM_REPO_URL, str(gram_dir)],
                check=False,
            )
            if clone.returncode != 0:
                print('  [CUIDADO] No se pudo descargar Gram para generar el parser AOT.', file=sys.stderr)
                return False

            build = subprocess.run(
                [
                    vnma_bin,
                    'run',
                    'tools/build_aot_parser.py',
                    '--gram-path',
                    str(gram_dir),
                    '--output-dir',
                    str(output_dir),
                ],
                cwd=str(target_dir),
                check=False,
            )
            if build.returncode != 0 or not _has_aot_parser(target_dir):
                print('  [CUIDADO] No se pudo construir la biblioteca AOT de Gram.', file=sys.stderr)
                return False
    except OSError as error:
        print(f'  [CUIDADO] Falló la preparación del parser AOT: {error}', file=sys.stderr)
        return False

    print('  [OK] Biblioteca AOT de Gram construida.')
    return True


def _bundled_compiler_dir() -> Path | None:
    """Directorio con Bagron, vendor y Gram AOT dentro del instalador."""
    if not getattr(sys, 'frozen', False):
        return None
    meipass = getattr(sys, '_MEIPASS', None)
    return Path(meipass) / 'bagron-payload' if meipass else None


def _prebuilt_layout(payload: Path, runtime: Path) -> tuple[str, Path]:
    """Valida el bundle antes de tocar el directorio de instalación."""
    info_path = payload / 'bagron-prebuilt.json'
    metadata = json.loads(info_path.read_text(encoding='utf-8'))
    if metadata.get('format_version') != 1:
        raise ValueError('Formato de bundle Bagron no compatible.')
    if metadata.get('bagron_version') != BAGRON_VERSION:
        raise ValueError('El bundle no corresponde a esta versión de Bagron.')
    expected_platform = _host_release_platform()
    if metadata.get('platform') != expected_platform:
        raise ValueError('El bundle corresponde a otra plataforma.')
    library_name = metadata.get('aot_library')
    if library_name not in _aot_library_names():
        raise ValueError('La biblioteca AOT del bundle no corresponde a este sistema.')

    # PyInstaller intentionally omits alias files; validate the manifest and
    # canonical targets before copying, then restore aliases at destination.
    aliases = verify_manifest(runtime, expected_platform=expected_platform)
    python_bin = _runtime_python_path(runtime)
    if not python_bin.is_file() and python_bin.relative_to(runtime).as_posix() not in aliases:
        raise FileNotFoundError('Falta el intérprete Python del runtime preparado.')

    library = payload / 'build' / 'aot' / library_name
    manifest = library.parent / 'gram_parser_manifest.json'
    requirements = (
        payload / 'main.py',
        payload / 'core' / 'version.py',
        payload / 'vnma.toml',
        payload / 'vendor' / 'gram',
        payload / 'vendor' / 'llvmlite',
        library,
        manifest,
    )
    if any(not item.exists() for item in requirements):
        raise FileNotFoundError('Faltan componentes del compilador preconstruido.')
    manifest_data = json.loads(manifest.read_text(encoding='utf-8'))
    expected_grammar = metadata.get('grammar_id')
    actual_grammar = manifest_data.get('grammar_id')
    try:
        expected_id = (int(expected_grammar, 0)
                       if isinstance(expected_grammar, str)
                       else int(expected_grammar))
        actual_id = (int(actual_grammar, 0)
                     if isinstance(actual_grammar, str)
                     else int(actual_grammar))
    except (TypeError, ValueError) as error:
        raise ValueError('El manifiesto de Gram AOT tiene un grammar_id inválido.') from error
    if expected_id != actual_id:
        raise ValueError('El parser AOT no coincide con su manifiesto.')
    digest = hashlib.sha256(library.read_bytes()).hexdigest()
    if digest != metadata.get('aot_sha256'):
        raise ValueError('La biblioteca Gram AOT del bundle no pasó la verificación SHA-256.')
    return library_name, _runtime_python_path(runtime)


def _remove_install_path(path: Path) -> None:
    """Remove one managed path without following symbolic links."""
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _remove_legacy_install_paths(target_dir: Path) -> None:
    """Remove global module state that is no longer part of an installation."""
    legacy_modules = target_dir / 'modules'
    _assert_managed_path_is_local(target_dir, legacy_modules)
    if legacy_modules.exists() or legacy_modules.is_symlink():
        _remove_install_path(legacy_modules)


def _assert_managed_path_is_local(target_dir: Path, path: Path) -> None:
    """Reject managed destinations whose parent tree redirects outside install."""
    try:
        path.relative_to(target_dir)
    except ValueError as error:
        raise OSError(f'La ruta administrada escapa de la instalación: {path}') from error
    current = path.parent
    while True:
        if current.is_symlink():
            raise OSError(f'La ruta administrada contiene un enlace simbólico: {current}')
        if current == target_dir:
            break
        if current.parent == current:
            raise OSError(f'La ruta administrada no pertenece a la instalación: {path}')
        current = current.parent


def _stage_prebuilt_installation(
    payload: Path,
    runtime: Path,
    target_dir: Path,
) -> Path:
    """Prepare and validate a complete prebuilt installation in a sibling temp tree."""
    staging = Path(tempfile.mkdtemp(prefix=f'.{target_dir.name}-stage-', dir=target_dir.parent))
    try:
        for entry in payload.iterdir():
            destination = staging / entry.name
            if entry.is_dir():
                shutil.copytree(entry, destination, symlinks=True)
            else:
                shutil.copy2(entry, destination)
        staged_libraries = staging / 'libs'
        if staged_libraries.exists():
            from core.library import LibraryError, verify_library

            if staged_libraries.is_symlink() or not staged_libraries.is_dir():
                raise OSError('La carpeta libs del bundle no es un directorio seguro.')
            for library in staged_libraries.iterdir():
                if library.is_symlink() or not library.is_file() or library.suffix.lower() != '.lib':
                    raise OSError(f'El bundle contiene una entrada inválida en libs: {library.name!r}')
                try:
                    verify_library(library)
                except LibraryError as error:
                    raise OSError(f'La librería incluida {library.name!r} no es válida: {error}') from error
        shutil.copytree(runtime, staging / LOCAL_RUNTIME_NAME, symlinks=True)
        restore_aliases(
            staging / LOCAL_RUNTIME_NAME,
            platform=_host_release_platform(),
        )
        _create_launchers(staging / 'bin')

        python_bin = _runtime_python_path(staging / LOCAL_RUNTIME_NAME)
        probe_environment = os.environ.copy()
        probe_environment['PYTHONPATH'] = os.pathsep.join(
            [str(staging / 'vendor'), probe_environment.get('PYTHONPATH', '')]
        )
        probe = subprocess.run(
            [str(python_bin), str(staging / 'main.py'), '--version'],
            cwd=str(staging),
            capture_output=True,
            text=True,
            env=probe_environment,
            check=False,
        )
        if probe.returncode != 0 or f'Bagron {BAGRON_VERSION}' not in probe.stdout:
            detail = (probe.stderr or probe.stdout).strip()
            raise OSError(
                'El compilador preparado no superó la verificación'
                + (f': {detail}' if detail else '.')
            )
        return staging
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _commit_prebuilt_installation(staging: Path, target_dir: Path) -> None:
    """Replace managed paths atomically enough to restore the old install on error."""
    backup = Path(tempfile.mkdtemp(prefix=f'.{target_dir.name}-backup-', dir=target_dir.parent))
    moved_old: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    relative_paths = (*_PREBUILT_MANAGED_PATHS, *_LEGACY_INSTALL_PATHS)
    try:
        for relative in relative_paths:
            destination = target_dir / relative
            _assert_managed_path_is_local(target_dir, destination)
            staged = staging / relative
            backup_path = backup / relative
            if staged.exists() or staged.is_symlink():
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists() or destination.is_symlink():
                    os.replace(destination, backup_path)
                    moved_old.append((destination, backup_path))
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged, destination)
                installed.append(destination)
            elif destination.exists() or destination.is_symlink():
                # Managed paths absent from the new payload are stale compiler
                # state and must not survive an upgrade.  ``libs/`` is kept
                # outside this list so explicitly installed project packages
                # remain untouched.
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                os.replace(destination, backup_path)
                moved_old.append((destination, backup_path))

        libraries = target_dir / 'libs'
        _assert_managed_path_is_local(target_dir, libraries)
        if libraries.is_symlink() or (libraries.exists() and not libraries.is_dir()):
            raise OSError(f'La carpeta de librerías no es un directorio seguro: {libraries}')
        libraries.mkdir(parents=True, exist_ok=True)
        staged_libraries = staging / 'libs'
        if staged_libraries.is_dir():
            for staged_library in sorted(staged_libraries.glob('*.lib')):
                destination = libraries / staged_library.name
                _assert_managed_path_is_local(target_dir, destination)
                backup_path = backup / 'libs' / staged_library.name
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists() or destination.is_symlink():
                    os.replace(destination, backup_path)
                    moved_old.append((destination, backup_path))
                temporary_library = libraries / f'.{staged_library.stem}.stage.tmp'
                try:
                    shutil.copy2(staged_library, temporary_library)
                    os.replace(temporary_library, destination)
                finally:
                    temporary_library.unlink(missing_ok=True)
                installed.append(destination)
    except Exception:
        for destination in reversed(installed):
            try:
                _remove_install_path(destination)
            except OSError:
                pass
        for destination, backup_path in reversed(moved_old):
            if not backup_path.exists() and not backup_path.is_symlink():
                continue
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(backup_path, destination)
            except OSError:
                pass
        raise
    finally:
        shutil.rmtree(backup, ignore_errors=True)
        shutil.rmtree(staging, ignore_errors=True)


def _install_prebuilt(target_dir: Path) -> int:
    """Instala archivos precompilados sin red, pip ni reconstrucción de Gram."""
    payload = _bundled_compiler_dir()
    runtime = _bundled_python_dir()
    if payload is None or runtime is None:
        print('Error: el instalador no contiene su bundle preconstruido.', file=sys.stderr)
        return 1
    try:
        _prebuilt_layout(payload, runtime)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f'Error: el bundle preconstruido es inválido: {error}', file=sys.stderr)
        return 1

    print('\n[1/3] Preparando compilador, vendor y Gram AOT preparados...')
    try:
        staging = _stage_prebuilt_installation(payload, runtime, target_dir)
        _commit_prebuilt_installation(staging, target_dir)
        print('  [OK] Bundle validado y reemplazado de forma transaccional.')
    except (OSError, ValueError) as error:
        print(f'Error: no se pudo instalar el bundle sin dejar cambios parciales: {error}', file=sys.stderr)
        return 1

    print('[2/3] Verificando la CLI preparada sin conexión...')
    print('  [OK] Bagron y el runtime portable superaron la verificación en staging.')

    print('[3/3] Configurando el PATH de usuario...')
    try:
        bin_dir = target_dir / 'bin'
        if os.name == 'posix':
            _add_to_posix_user_path(bin_dir)
        else:
            _add_to_windows_user_path(bin_dir)
    except OSError as error:
        print(f'Error: no se pudo crear el lanzador: {error}', file=sys.stderr)
        return 1

    print(f'Instalación preconstruida completada: {target_dir}')
    return 0


def install(
    target_dir: Path | None = None,
    *,
    from_local: bool = False,
) -> int:
    """Instala Bagron en target_dir."""
    source_root = Path(__file__).resolve().parent

    if target_dir is None:
        target_dir = Path.home() / DEFAULT_INSTALL_NAME

    try:
        target_dir = _resolve_local_target(target_dir)
    except OSError as error:
        print(f'Error: la ruta de instalación no es segura: {error}', file=sys.stderr)
        return 1
    print(f'=== Instalador de Bagron {BAGRON_VERSION} ===')
    frozen = bool(getattr(sys, 'frozen', False))
    mode = ('Preconstruido (sin red)' if frozen and not from_local
            else 'Local (copia directa)' if from_local
            else 'GitHub (' + BAGRON_REPO_URL + ')')
    print(f'Modo:    {mode}')
    print(f'Destino: {target_dir}')

    if frozen and from_local:
        print('Error: --local solo es compatible con la instalación desde fuentes.', file=sys.stderr)
        return 1
    if frozen:
        target_dir.mkdir(parents=True, exist_ok=True)
        return _install_prebuilt(target_dir)

    target_dir.mkdir(parents=True, exist_ok=True)

    # Paso 1: Obtención de fuentes
    try:
        if from_local:
            print('\n[1/7] Copiando componentes del compilador desde la copia local...')
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

            for filename in FILES_TO_COPY:
                src_file = source_root / filename
                if src_file.is_file():
                    shutil.copy2(src_file, target_dir / filename)

            _remove_legacy_install_paths(target_dir)
        else:
            print('\n[1/7] Obteniendo Bagron desde GitHub...')
            _fetch_from_github(target_dir)
            _remove_legacy_install_paths(target_dir)
    except (OSError, subprocess.CalledProcessError, urllib.error.URLError, zipfile.BadZipFile) as error:
        print(f'\nError: no se pudieron obtener las fuentes de Bagron: {error}', file=sys.stderr)
        return 1

    # Sincronizar main.py local si contiene soporte para -o y --execute
    src_main = source_root / 'main.py'
    if src_main.is_file():
        shutil.copy2(src_main, target_dir / 'main.py')

    # Paso 2: Configuración de vnma.toml
    print('\n[2/7] Configurando vnma.toml con dependencia remota a Gram...')
    _configure_vnma_toml(target_dir)
    print(f'  [OK] vnma.toml configurado para apuntar a: {GRAM_REPO_URL}')

    # Paso 3: Preparación del runtime y del gestor local de dependencias
    print('\n[3/7] Preparando el Python portable y el entorno local de vnma...')
    vnma_bin = _bootstrap_vnma(target_dir)
    if vnma_bin is None:
        return 1
    print(f'  [OK] Python y vnma aislados en: {vnma_bin.parent}')

    # Paso 4: Resolución de Gram y llvmlite con el gestor local
    print('\n[4/7] Resolviendo e instalando Gram y llvmlite con vnma...')
    install_res = subprocess.run([vnma_bin, 'install'], cwd=str(target_dir), check=False)
    if install_res.returncode != 0:
        print(
            '\nError: "vnma install" terminó con código de error.\n'
            f'Reintenta manualmente con: cd "{target_dir}" && vnma install',
            file=sys.stderr,
        )
        return 1
    print('  [OK] Dependencias instaladas y sincronizadas en vendor/.')

    # Paso 5: El frontend AOT no tiene un fallback Python; debe estar incluido
    # en el paquete o generarse con las fuentes nativas de Gram y Clang.
    if not _build_aot_parser(target_dir, vnma_bin):
        print(
            '\nError: Bagron no puede continuar sin su biblioteca AOT/FFI de Gram.',
            file=sys.stderr,
        )
        return 1

    # Paso 6: Creación de la carpeta base de librerías
    print('\n[6/7] Creando la carpeta base libs/...')
    for empty_name in EMPTY_DIRS:
        empty_path = target_dir / empty_name
        empty_path.mkdir(parents=True, exist_ok=True)

    # Paso 7: Generación de lanzadores y configuración de PATH
    print('\n[7/7] Generando lanzadores CLI en bin/ y configurando el PATH...')
    bin_dir = target_dir / 'bin'
    _create_launchers(bin_dir)

    if os.name == 'posix':
        added_to_path = _add_to_posix_user_path(bin_dir)
        if added_to_path:
            print(f'  [OK] Lanzadores instalados en {Path.home() / ".local" / "bin"}')
            print('  [NOTA] Si el comando no aparece, añade ~/.local/bin a tu PATH.')
        else:
            print('  [NOTA] Añade manualmente el directorio ~/.local/bin al PATH.')
    else:
        added_to_path = _add_to_windows_user_path(bin_dir)
        if added_to_path:
            print(f'  [OK] Ruta añadida al PATH de usuario: {bin_dir}')
        else:
            print(f'  [OK] La ruta ya se encontraba en el PATH: {bin_dir}')

    print('\n¡Instalación completada con éxito!')
    if os.name == 'posix':
        print('Ahora puedes abrir una nueva terminal y ejecutar:')
        print('  bagron "ruta/a/archivo.bg" -o programa')
        print('  bagron --execute "ruta/a/archivo.bg" -o programa\n')
    else:
        print('Ahora puedes abrir una nueva terminal y ejecutar:')
        print('  bagron "ruta/a/archivo.bg" -o programa.exe')
        print('  bagron --execute "ruta/a/archivo.bg" -o programa.exe\n')
    return 0


def _schedule_windows_cleanup(target_dir: Path) -> bool:
    """Programa la eliminación diferida cuando Windows mantiene archivos abiertos."""
    if os.name != 'nt':
        return False

    cleanup_script: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w',
            encoding='utf-8',
            suffix='.cmd',
            prefix='bagron-uninstall-',
            delete=False,
        ) as script:
            cleanup_script = Path(script.name)
            script.write(
                '@echo off\r\n'
                'setlocal\r\n'
                'set "TARGET=%~1"\r\n'
                'for /L %%N in (1,1,60) do (\r\n'
                '  rmdir /S /Q "%TARGET%" >nul 2>&1\r\n'
                '  if not exist "%TARGET%" goto done\r\n'
                '  ping 127.0.0.1 -n 2 >nul\r\n'
                ')\r\n'
                ':done\r\n'
                'del /F /Q "%~f0" >nul 2>&1\r\n'
            )

        comspec = os.environ.get('ComSpec', 'cmd.exe')
        flags = _windows_no_window_flags()
        subprocess.Popen(
            [comspec, '/D', '/C', str(cleanup_script), str(target_dir)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            cwd=str(cleanup_script.parent),
            creationflags=flags,
        )
        return True
    except OSError:
        if cleanup_script is not None:
            cleanup_script.unlink(missing_ok=True)
        return False


def _safe_uninstall_target(target_dir: Path) -> bool:
    """Evita que una ruta raíz o el perfil completo sean objetivos de borrado."""
    try:
        resolved = _resolve_local_target(target_dir)
    except OSError:
        return False
    return resolved != Path(resolved.anchor) and resolved != Path.home().resolve()


def uninstall(target_dir: Path | None = None) -> int:
    """Desinstala Bagron, limpia enlaces y PATH y elimina su instalación."""
    if target_dir is None:
        target_dir = Path.home() / DEFAULT_INSTALL_NAME

    if not _safe_uninstall_target(target_dir):
        print(f'Error: la ruta de desinstalación no es segura: {target_dir}', file=sys.stderr)
        return 1
    target_dir = _resolve_local_target(target_dir)
    bin_dir = target_dir / 'bin'

    print(f'=== Desinstalador de Bagron ===')
    print(f'Objetivo: {target_dir}')

    if os.name == 'posix':
        removed = _remove_from_posix_user_path(bin_dir)
        if removed:
            print(f'  [OK] Lanzadores retirados de {Path.home() / ".local" / "bin"}')
        else:
            print('  - No había enlaces POSIX asociados a esta instalación.')
    else:
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
            if _schedule_windows_cleanup(target_dir):
                print('  [OK] La limpieza de Windows continuará al cerrar Bagron.')
                return 0
            print(f'  Error al eliminar {target_dir}: {error}', file=sys.stderr)
            return 1

    print('Desinstalación finalizada.')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=f'Instalador de Bagron {BAGRON_VERSION}')
    parser.add_argument(
        '--target',
        type=Path,
        default=None,
        help='Directorio de destino (por defecto: carpeta Bagron del usuario)',
    )
    parser.add_argument(
        '--local',
        action='store_true',
        help='Instala desde la copia local en lugar de descargar desde GitHub',
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        '--uninstall',
        action='store_true',
        help='Desinstala Bagron y elimina la ruta del PATH',
    )
    actions.add_argument(
        '--update',
        action='store_true',
        help='Actualiza la instalación a la última release estable de GitHub',
    )
    args = parser.parse_args()

    try:
        if args.uninstall:
            return uninstall(args.target)
        if args.update:
            return update(args.target)
        return install(args.target, from_local=args.local)
    except (OSError, subprocess.CalledProcessError, urllib.error.URLError, zipfile.BadZipFile) as error:
        print(f'Error de instalación: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
