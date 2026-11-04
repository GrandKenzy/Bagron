"""Instalador y configurador de entorno para Bagron.

Descarga o actualiza Bagron desde un release de GitHub (o sincroniza
localmente), configura las dependencias en vnma.toml con Gram remoto, extrae
un runtime Python portable, resuelve el entorno vendor mediante vnma aislado,
crea carpetas base y registra la CLI en el PATH de usuario.
"""

from __future__ import annotations

import argparse
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile


# ============================================================================
# Constantes y repositorios remotos
# ============================================================================

DEFAULT_INSTALL_NAME = 'Bagron'
BAGRON_VERSION = '1.0.4'
BAGRON_REPO_URL = 'https://github.com/GrandKenzy/Bagron.git'
BAGRON_ZIP_URL = f'https://github.com/GrandKenzy/Bagron/archive/refs/tags/{BAGRON_VERSION}.zip'
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
EMPTY_DIRS = ('libs', 'modules')


# ============================================================================
# Entorno local de vnma
# ============================================================================

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
        # NOTA: Solo el modo fuente usa una venv del Python del sistema. El
        # ejecutable compilado debe llevar siempre portable-python dentro.
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

    for name in ('bagron', 'Bagron'):
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
    removed = False
    for name in ('bagron', 'Bagron'):
        link = user_bin / name
        if not link.is_symlink():
            continue
        try:
            if link.resolve() == (bin_path / name).resolve():
                link.unlink()
                removed = True
        except OSError:
            continue
    return removed


# ============================================================================
# Generación de lanzadores de comandos
# ============================================================================

def _create_launchers(bin_dir: Path) -> None:
    """Crea los lanzadores nativos para Windows o sistemas POSIX."""
    bin_dir.mkdir(parents=True, exist_ok=True)

    if os.name == 'posix':
        shell_content = '''#!/usr/bin/env bash
set -euo pipefail

launcher_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
bagron_home="$(CDPATH= cd -- "$launcher_dir/.." && pwd)"
python_bin="$bagron_home/.runtime/bin/python"
if [[ ! -x "$python_bin" ]]; then
    printf '%s\n' 'Error: falta el Python portable de Bagron; ejecuta el instalador de Bagron de nuevo.' >&2
    exit 1
fi
export BAGRON_CALLER_DIR="$PWD"
cd "$bagron_home"
exec "$python_bin" -m vnma run main.py "$@"
'''
        for name in ('bagron', 'Bagron'):
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
        'pushd "%BAGRON_HOME%"\r\n'
        '"%PYTHON%" -m vnma run main.py %*\r\n'
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
        '$env:BAGRON_CALLER_DIR = $callerDir\r\n'
        'Push-Location $bagronHome\r\n'
        'try {\r\n'
        '    & $python -m vnma run main.py @args\r\n'
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
# Descarga y sincronización desde GitHub
# ============================================================================

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
        with urllib.request.urlopen(BAGRON_ZIP_URL) as response:
            zip_bytes = response.read()

        print('  [HTTP] Extrayendo archivos del release...')
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            prefix = zf.namelist()[0].split('/')[0] + '/'
            for member in zf.infolist():
                if member.filename == prefix:
                    continue
                relative_path = member.filename[len(prefix):]
                if not relative_path:
                    continue
                out_path = target_dir / relative_path
                if member.is_dir():
                    out_path.mkdir(parents=True, exist_ok=True)
                else:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, open(out_path, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
    except Exception as error:
        print(f'Error al descargar desde GitHub: {error}', file=sys.stderr)
        raise


# ============================================================================
# Configuración de vnma.toml
# ============================================================================

def _configure_vnma_toml(target_dir: Path) -> None:
    """Configura vnma.toml para apuntar a la dependencia remota de Gram."""
    # NOTA: Se asegura que gram use la URL canónica de GitHub con rama main.
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
        # CUIDADO: un lock local puede contener Gram editable desde ~/Desktop/Gram.
        stale_lock.unlink()


def _aot_library_names() -> tuple[str, ...]:
    """Devuelve los nombres de biblioteca AOT esperados en la plataforma actual."""
    if sys.platform == 'win32':
        return ('bagron_aot.dll',)
    if sys.platform == 'darwin':
        return ('bagron_aot.dylib', 'libbagron_aot.dylib')
    return ('libbagron_aot.so', 'bagron_aot.so')


def _has_aot_parser(target_dir: Path) -> bool:
    """Comprueba si la instalación ya contiene la biblioteca AOT y su manifiesto."""
    output_dir = target_dir / 'build' / 'aot'
    return (
        any((output_dir / name).is_file() for name in _aot_library_names())
        and (output_dir / 'gram_parser_manifest.json').is_file()
    )


def _build_aot_parser(target_dir: Path, vnma_bin: Path | None) -> bool:
    """Genera la biblioteca FFI de Gram cuando el paquete no trae un binario."""
    if _has_aot_parser(target_dir):
        print('  [OK] Biblioteca AOT de Gram incluida en la distribución.')
        return True

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


# ============================================================================
# Proceso principal de instalación
# ============================================================================

def install(
    target_dir: Path | None = None,
    *,
    from_local: bool = False,
) -> int:
    """Instala Bagron en target_dir."""
    source_root = Path(__file__).resolve().parent

    if target_dir is None:
        target_dir = Path.home() / DEFAULT_INSTALL_NAME

    target_dir = target_dir.resolve()
    print(f'=== Instalador de Bagron {BAGRON_VERSION} ===')
    print(f'Modo:    {"Local (copia directa)" if from_local else "GitHub (" + BAGRON_REPO_URL + ")"}')
    print(f'Destino: {target_dir}')

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
        else:
            print('\n[1/7] Obteniendo Bagron desde GitHub...')
            _fetch_from_github(target_dir)
    except (OSError, subprocess.CalledProcessError, urllib.error.URLError, zipfile.BadZipFile) as error:
        print(f'\nError: no se pudieron obtener las fuentes de Bagron: {error}', file=sys.stderr)
        return 1

    # NOTA: Si el directorio local o de ejecución contiene build/aot (driver FFI nativo), sincronizarlo.
    src_aot = source_root / 'build' / 'aot'
    if src_aot.is_dir():
        dst_aot = target_dir / 'build' / 'aot'
        shutil.copytree(src_aot, dst_aot, dirs_exist_ok=True)

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

    # Paso 6: Creación de carpetas base libs/ y modules/
    print('\n[6/7] Creando carpetas base libs/ y modules/...')
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

    if os.name == 'posix':
        removed = _remove_from_posix_user_path(bin_dir)
        if removed:
            print(f'  [OK] Lanzadores retirados de {Path.home() / ".local" / "bin"}')
        else:
            print('  - No había enlaces POSIX asociados a esta instalación.')
    elif bin_dir.exists():
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
    parser.add_argument(
        '--uninstall',
        action='store_true',
        help='Desinstala Bagron y elimina la ruta del PATH',
    )
    args = parser.parse_args()

    try:
        if args.uninstall:
            return uninstall(args.target)
        return install(args.target, from_local=args.local)
    except (OSError, subprocess.CalledProcessError, urllib.error.URLError, zipfile.BadZipFile) as error:
        print(f'Error de instalación: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
