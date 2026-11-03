"""Instalador y configurador de entorno para Bagron.

Descarga o actualiza Bagron desde un release de GitHub (o sincroniza
localmente), configura las dependencias en vnma.toml con Gram remoto, resuelve
el entorno vendor mediante vnma, crea carpetas base y registra la CLI en el
PATH de usuario.
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
import urllib.request
import zipfile


# ============================================================================
# Constantes y repositorios remotos
# ============================================================================

DEFAULT_INSTALL_NAME = 'Bagron'
BAGRON_VERSION = '1.0.3'
BAGRON_REPO_URL = 'https://github.com/GrandKenzy/Bagron.git'
BAGRON_ZIP_URL = f'https://github.com/GrandKenzy/Bagron/archive/refs/tags/{BAGRON_VERSION}.zip'
GRAM_REPO_URL = 'https://github.com/GrandKenzy/Gram.git'

SUBDIRS_TO_COPY = (
    'core',
    'tools',
    'vendor',
    'examples',
    'docs',
    'badge',
    'changelog',
)
FILES_TO_COPY = (
    'main.py',
    'vnma.toml',
    'vnma.lock',
    'README.md',
    'LICENSE',
    'install.sh',
)
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
export BAGRON_CALLER_DIR="$PWD"
cd "$bagron_home"
exec vnma run main.py "$@"
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
        'pushd "%BAGRON_HOME%"\r\n'
        'vnma run main.py %*\r\n'
        'set "EXIT_CODE=%ERRORLEVEL%"\r\n'
        'popd\r\n'
        'exit /b %EXIT_CODE%\r\n'
    )

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
            subprocess.run(
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
                check=True,
            )
            return

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


def _build_aot_parser(target_dir: Path, vnma_bin: str | None) -> bool:
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

    print('\n[4/6] Construyendo la biblioteca AOT/FFI de Gram...')
    output_dir = target_dir / 'build' / 'aot'
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
    if from_local:
        print('\n[1/6] Copiando componentes del compilador desde la copia local...')
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
        print('\n[1/6] Obteniendo Bagron desde GitHub...')
        _fetch_from_github(target_dir)

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
    print('\n[2/6] Configurando vnma.toml con dependencia remota a Gram...')
    _configure_vnma_toml(target_dir)
    print(f'  [OK] vnma.toml configurado para apuntar a: {GRAM_REPO_URL}')

    # Paso 3: Resolución de dependencias con vnma
    print('\n[3/6] Resolviendo e instalando dependencias con vnma...')
    vnma_bin = shutil.which('vnma')
    if vnma_bin:
        install_res = subprocess.run([vnma_bin, 'install'], cwd=str(target_dir))
        if install_res.returncode != 0:
            print(
                '\n# CUIDADO: "vnma install" terminó con código de error.\n'
                f'Puedes reintentar manualmente con: cd "{target_dir}" && vnma install',
                file=sys.stderr,
            )
        else:
            print('  [OK] Dependencias instaladas y sincronizadas en vendor/.')
    else:
        print(
            '\n# CUIDADO: "vnma" no se detectó en el PATH.\n'
            'Instala vnma para restaurar las dependencias del compilador.',
            file=sys.stderr,
        )

    # Paso 4: El frontend AOT no tiene un fallback Python; debe estar incluido
    # en el paquete o generarse con las fuentes nativas de Gram y Clang.
    _build_aot_parser(target_dir, vnma_bin)

    # Paso 5: Creación de carpetas base libs/ y modules/
    print('\n[5/6] Creando carpetas base libs/ y modules/...')
    for empty_name in EMPTY_DIRS:
        empty_path = target_dir / empty_name
        empty_path.mkdir(parents=True, exist_ok=True)

    # Paso 6: Generación de lanzadores y configuración de PATH
    print('\n[6/6] Generando lanzadores CLI en bin/ y configurando el PATH...')
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

    if args.uninstall:
        return uninstall(args.target)
    return install(args.target, from_local=args.local)


if __name__ == '__main__':
    sys.exit(main())
