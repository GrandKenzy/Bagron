import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

# NOTA: Asegurar que la raíz de Bagron encabece sys.path y filtrar cualquier
# subcarpeta de dependencia vendoreada (como vendor/gram) que colisione con módulos del núcleo (core).
_PROJECT_ROOT = Path(__file__).resolve().parent
_VENDOR_GRAM = _PROJECT_ROOT / 'vendor' / 'gram'

sys.path = [
    str(_PROJECT_ROOT),
    *(
        p for p in sys.path
        if os.path.normcase(os.path.normpath(p)) != os.path.normcase(os.path.normpath(str(_VENDOR_GRAM)))
        and os.path.normcase(os.path.normpath(p)) != os.path.normcase(os.path.normpath(str(_PROJECT_ROOT)))
    ),
]

from core.compiler import CompilationError, Compiler
from core.version import BAGRON_VERSION
from core.library import (
    LibraryError,
    inspect_library,
    pack_compiled_library,
    pack_library,
    sign_library_metadata,
    unpack_library,
    verify_library,
    verify_library_signature,
)


def _library_help() -> str:
    return (
        'Uso:\n'
        '  bagron library --v1 <source> -o <archivo.lib> [--name N] [--version V]\n'
        '  bagron library --v2 <source> -o <archivo.lib> [--name N] [--version V]\n'
        '  bagron inspect <archivo.lib>\n'
        '  bagron verify <archivo.lib>\n'
        '  bagron sign <directorio>\n'
        '  bagron unpack <archivo.lib> <destino>'
    )


def _install_help() -> str:
    return (
        'Uso:\n'
        '  bagron install --library --v1 <source> [--name N] [--version V]\n'
        '  bagron install --library --v2 <source> [--name N] [--version V]\n'
        '  bagron install --module <archivo.bg|carpeta>'
    )


def _main_help() -> str:
    return (
        'Uso:\n'
        '  bagron <archivo.bg> [-o <salida>] [--execute] [--strict-ownership]\n'
        '  bagron --version\n'
        '  bagron --update                       Actualiza a la última release estable de GitHub.\n'
        '  bagron --uninstall                    Elimina la instalación actual y sus lanzadores.\n\n'
        'Instalación local (libs y modules):\n'
        + _install_help() + '\n\n'
        'Soporte de editor (VS Code):\n'
        '  bagron --vscode install                 Instala o reinstala limpiamente la extensión oficial en VS Code.\n\n'
        'Comandos de librería:\n'
        + _library_help() + '\n\n'
        'Repositorios de alojamiento:\n'
        '  bagron build --hostutils [ruta]          Sincroniza versiones y hashes de build/ en discentra_central/.'
    )


def _find_code_executable() -> str | None:
    """Busca el ejecutable del CLI de VS Code ('code' o 'code.cmd')."""
    code_bin = shutil.which('code') or shutil.which('code.cmd')
    if code_bin:
        return code_bin

    if sys.platform == 'win32':
        candidates = [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Microsoft VS Code' / 'bin' / 'code.cmd',
            Path(os.environ.get('ProgramFiles', '')) / 'Microsoft VS Code' / 'bin' / 'code.cmd',
            Path(os.environ.get('ProgramFiles(x86)', '')) / 'Microsoft VS Code' / 'bin' / 'code.cmd',
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)

    return None


def _find_bundled_vsix() -> Path | None:
    """Localiza el archivo .vsix empaquetado en Bagron."""
    canonical = _PROJECT_ROOT / 'tools' / 'vscode' / 'bagron-language-support.vsix'
    if canonical.is_file():
        return canonical

    vscode_dir = _PROJECT_ROOT / 'tools' / 'vscode'
    if vscode_dir.is_dir():
        vsix_files = sorted(vscode_dir.glob('*.vsix'), reverse=True)
        if vsix_files:
            return vsix_files[0]

    return None


def _vscode_command(argv: list[str]) -> int:
    """Gestiona el comando `bagron --vscode install`."""
    subcommand = argv[1] if len(argv) > 1 else 'install'
    if subcommand in {'-h', '--help'}:
        print('Uso:\n  bagron --vscode install    Instala o reinstala limpiamente la extensión oficial en VS Code.')
        return 0

    if subcommand != 'install':
        print(
            f"Error: Subcomando desconocido para --vscode: '{subcommand}'. Uso: bagron --vscode install",
            file=sys.stderr,
        )
        return 2

    code_bin = _find_code_executable()
    if not code_bin:
        print(
            'Error: No se encontró el ejecutable CLI de VS Code ("code"). '
            'Asegúrate de que VS Code esté instalado y disponible en el sistema.',
            file=sys.stderr,
        )
        return 1

    vsix_path = _find_bundled_vsix()
    if not vsix_path or not vsix_path.is_file():
        print(
            f'Error: No se encontró el paquete .vsix en {_PROJECT_ROOT / "tools" / "vscode"}.',
            file=sys.stderr,
        )
        return 1

    extension_id = 'bagron-dev.bagron-language-support'

    print('[*] Comprobando extensiones instaladas en VS Code...')
    try:
        list_proc = subprocess.run(
            [code_bin, '--list-extensions'],
            capture_output=True,
            text=True,
            check=False,
            shell=sys.platform == 'win32',
        )
        installed = [
            line.strip().lower()
            for line in list_proc.stdout.splitlines()
            if line.strip()
        ]
    except Exception as error:
        print(f'Advertencia al consultar extensiones: {error}', file=sys.stderr)
        installed = []

    if extension_id.lower() in installed:
        print(f'[*] Desinstalando versión anterior de {extension_id} para una instalación limpia...')
        try:
            uninst_proc = subprocess.run(
                [code_bin, '--uninstall-extension', extension_id],
                capture_output=True,
                text=True,
                check=False,
                shell=sys.platform == 'win32',
            )
            if uninst_proc.returncode == 0:
                print(f'[+] Versión anterior desinstalada correctamente.')
            else:
                print(f'Advertencia al desinstalar: {uninst_proc.stderr.strip()}', file=sys.stderr)
        except Exception as error:
            print(f'Advertencia al desinstalar: {error}', file=sys.stderr)

    print(f'[*] Instalando paquete {vsix_path.name} en VS Code...')
    try:
        inst_proc = subprocess.run(
            [code_bin, '--install-extension', str(vsix_path), '--force'],
            capture_output=True,
            text=True,
            check=False,
            shell=sys.platform == 'win32',
        )
        if inst_proc.returncode == 0:
            print(f'[OK] ¡Extensión {extension_id} instalada con éxito en VS Code!')
            return 0
        else:
            print(f'Error al instalar la extensión:\n{inst_proc.stderr}', file=sys.stderr)
            return inst_proc.returncode
    except Exception as error:
        print(f'Error al ejecutar la instalación: {error}', file=sys.stderr)
        return 1


def _parse_compile_args(
    argv: list[str],
) -> tuple[str | None, str | None, bool, str | None]:
    """Extrae objetivo, ruta de salida y opción de ejecución.

    Retorna: (source, output_path, execute, error_message)
    """
    execute = False
    output_path = None
    sources: list[str] = []

    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in ('--execute', '-e'):
            execute = True
            index += 1
        elif arg in ('-o', '--output'):
            if index + 1 >= len(argv):
                return None, None, False, 'Error: la opción -o requiere especificar una ruta de salida'
            output_path = argv[index + 1]
            index += 2
        elif arg.startswith('-o') and len(arg) > 2:
            output_path = arg[2:]
            index += 1
        elif arg.startswith('-'):
            return None, None, False, f'Opción no admitida: {arg}'
        else:
            sources.append(arg)
            index += 1

    if not sources:
        return None, None, False, 'Error: No se especificó el archivo o módulo fuente a compilar'
    if len(sources) > 1:
        return (
            None,
            None,
            False,
            f'Error: Solo se admite un objetivo a la vez (recibidos: {len(sources)})',
        )

    return sources[0], output_path, execute, None


def _library_command(argv: list[str]) -> int:
    command = argv[0]
    caller_dir = Path(os.environ.get('BAGRON_CALLER_DIR', os.getcwd())).resolve()
    try:
        if command == 'library':
            selected = [flag for flag in ('--v1', '--v2') if flag in argv]
            if len(selected) != 1 or '-o' not in argv:
                print(_library_help(), file=sys.stderr)
                return 2
            version_flag = selected[0]

            name = None
            version = '0.1.0'
            output = None
            source = None

            index = 1
            while index < len(argv):
                arg = argv[index]
                if arg in ('--v1', '--v2'):
                    index += 1
                elif arg == '-o' and index + 1 < len(argv):
                    output = argv[index + 1]
                    index += 2
                elif arg == '--name' and index + 1 < len(argv):
                    name = argv[index + 1]
                    index += 2
                elif arg == '--version' and index + 1 < len(argv):
                    version = argv[index + 1]
                    index += 2
                elif not arg.startswith('-') and source is None:
                    source = arg
                    index += 1
                else:
                    index += 1

            if not source or not output:
                print(_library_help(), file=sys.stderr)
                return 2

            source_path = Path(source)
            if not source_path.is_absolute():
                source_path = (caller_dir / source_path).resolve()
            output_path = Path(output)
            if not output_path.is_absolute():
                output_path = (caller_dir / output_path).resolve()

            packer = pack_compiled_library if version_flag == '--v2' else pack_library
            result = packer(source_path, output_path, name=name, version=version)
            print(result)
            return 0
        if command == 'inspect' and len(argv) == 2:
            inspect_path = Path(argv[1])
            if not inspect_path.is_absolute():
                inspect_path = (caller_dir / inspect_path).resolve()
            print(json.dumps(
                inspect_library(inspect_path),
                ensure_ascii=False,
                indent=2,
            ))
            return 0
        if command == 'sign' and len(argv) == 2:
            sign_path = Path(argv[1])
            if not sign_path.is_absolute():
                sign_path = (caller_dir / sign_path).resolve()
            sig = sign_library_metadata(sign_path)
            print(f'OK {sign_path.name} {sig}')
            return 0
        if command == 'verify' and len(argv) == 2:
            verify_path = Path(argv[1])
            if not verify_path.is_absolute():
                verify_path = (caller_dir / verify_path).resolve()
            if verify_path.is_dir():
                valid, msg = verify_library_signature(verify_path)
                if not valid:
                    print(f'Verification failed: {msg}', file=sys.stderr)
                    return 1
                print(f'OK {verify_path.name} {msg}')
                return 0
            package = verify_library(verify_path)
            print(f'OK {package.name} v{package.library_version} {package.package_id}')
            return 0
        if command == 'unpack' and len(argv) == 3:
            unpack_src = Path(argv[1])
            if not unpack_src.is_absolute():
                unpack_src = (caller_dir / unpack_src).resolve()
            unpack_dest = Path(argv[2])
            if not unpack_dest.is_absolute():
                unpack_dest = (caller_dir / unpack_dest).resolve()
            print(unpack_library(unpack_src, unpack_dest))
            return 0
    except LibraryError as error:
        print(f'Library failed: {error}', file=sys.stderr)
        return 1
    print(_library_help(), file=sys.stderr)
    return 2


def _install_command(argv: list[str]) -> int:
    """Instala una librería en libs/ o un módulo en modules/ reemplazando lo existente."""
    if len(argv) < 2 or any(flag in argv for flag in ('-h', '--help')):
        print(_install_help())
        return 0

    caller_dir = Path(os.environ.get('BAGRON_CALLER_DIR', os.getcwd())).resolve()
    tokens = argv[1:]

    is_module = (
        '--module' in tokens
        or '--modules' in tokens
        or 'module' in tokens
        or 'modules' in tokens
    )
    is_library = (
        '--library' in tokens
        or 'library' in tokens
        or '--v1' in tokens
        or '--v2' in tokens
    )

    if not is_module and not is_library:
        if any(tok.endswith('.bg') for tok in tokens if not tok.startswith('-')):
            is_module = True
        else:
            is_library = True

    if is_module:
        module_path_str = None
        for flag in ('--module', '--modules'):
            if flag in tokens:
                idx = tokens.index(flag)
                if idx + 1 < len(tokens):
                    module_path_str = tokens[idx + 1]
                break

        if module_path_str is None:
            for tok in tokens:
                if tok not in {'module', 'modules', '--module', '--modules'} and not tok.startswith('-'):
                    module_path_str = tok
                    break

        if module_path_str is None:
            print('Error: Se requiere especificar la ruta del módulo.', file=sys.stderr)
            print(_install_help(), file=sys.stderr)
            return 2

        source_path = Path(module_path_str)
        if not source_path.is_absolute():
            source_path = (caller_dir / source_path).resolve()

        if not source_path.exists():
            print(f'Error: No se encontró el módulo: {module_path_str}', file=sys.stderr)
            return 1

        dest_dir = caller_dir / 'modules'
        dest_dir.mkdir(parents=True, exist_ok=True)

        if source_path.is_file():
            dest_file = dest_dir / source_path.name
            shutil.copy2(source_path, dest_file)
            print(dest_file)
            return 0
        elif source_path.is_dir():
            dest_target = dest_dir / source_path.name
            if dest_target.exists():
                if dest_target.is_dir():
                    shutil.rmtree(dest_target)
                else:
                    dest_target.unlink()
            shutil.copytree(source_path, dest_target)
            print(dest_target)
            return 0
        else:
            print(f'Error: Ruta no válida para módulo: {module_path_str}', file=sys.stderr)
            return 1

    # Modo librería
    v1 = '--v1' in tokens
    v2 = '--v2' in tokens
    if v1 and v2:
        print('Error: Solo se puede especificar una versión (--v1 o --v2).', file=sys.stderr)
        return 2

    name = None
    version = '0.1.0'
    library_path_str = None

    idx = 0
    while idx < len(tokens):
        tok = tokens[idx]
        if tok in {'--library', 'library', '--v1', '--v2'}:
            idx += 1
        elif tok == '--name' and idx + 1 < len(tokens):
            name = tokens[idx + 1]
            idx += 2
        elif tok == '--version' and idx + 1 < len(tokens):
            version = tokens[idx + 1]
            idx += 2
        elif tok.startswith('-'):
            idx += 1
        else:
            if library_path_str is None:
                library_path_str = tok
            idx += 1

    if library_path_str is None:
        print('Error: Se requiere especificar la ruta de la librería.', file=sys.stderr)
        print(_install_help(), file=sys.stderr)
        return 2

    source_path = Path(library_path_str)
    if not source_path.is_absolute():
        source_path = (caller_dir / source_path).resolve()

    if not source_path.exists():
        print(f'Error: No se encontró la librería: {library_path_str}', file=sys.stderr)
        return 1

    dest_dir = caller_dir / 'libs'
    dest_dir.mkdir(parents=True, exist_ok=True)

    if name is None:
        if source_path.is_file() and source_path.suffix.lower() == '.lib':
            name = source_path.stem
        else:
            name = source_path.name

    dest_file = dest_dir / f'{name}.lib'

    if source_path.is_file() and source_path.suffix.lower() == '.lib':
        shutil.copy2(source_path, dest_file)
        print(dest_file)
        return 0

    if not v1 and not v2:
        print('Error: Se requiere especificar --v1 o --v2 para empaquetar la librería.', file=sys.stderr)
        print(_install_help(), file=sys.stderr)
        return 2

    if source_path.is_dir() and (source_path / 'meta.toml').is_file():
        is_valid, sig_msg = verify_library_signature(source_path)
        if not is_valid:
            print(f'Advertencia de seguridad: {sig_msg}', file=sys.stderr)
        else:
            print(f'[info] Firma de la libreria verificada: {sig_msg}')

    packer = pack_compiled_library if v2 else pack_library
    try:
        result = packer(source_path, dest_file, name=name, version=version)
        print(result)
        return 0
    except LibraryError as error:
        print(f'Library failed: {error}', file=sys.stderr)
        return 1


def _build_help() -> str:
    return (
        'Uso:\n'
        '  bagron build --hostutils [directorio] [--auto-patch] [--dry-run] [--set-version PKG=VER]\n\n'
        '  Sincroniza los artefactos de build/ con discentra_central/ (packages.toml y manifest.toml).'
    )


def _build_command(argv: list[str]) -> int:
    tokens = argv[1:]
    if not tokens or '--help' in tokens or '-h' in tokens:
        print(_build_help())
        return 0

    if '--hostutils' in tokens or 'hostutils' in tokens:
        from core.hosting import HostingError, run_hostutils

        caller_dir = Path(os.environ.get('BAGRON_CALLER_DIR', os.getcwd())).resolve()
        auto_patch = '--auto-patch' in tokens
        dry_run = '--dry-run' in tokens
        set_versions: dict[str, str] = {}
        target_dir = caller_dir

        idx = 0
        while idx < len(tokens):
            tok = tokens[idx]
            if tok in {'--hostutils', 'hostutils', '--auto-patch', '--dry-run'}:
                idx += 1
            elif tok == '--set-version' and idx + 1 < len(tokens):
                val = tokens[idx + 1]
                if '=' in val:
                    pkg_k, pkg_v = val.split('=', 1)
                    set_versions[pkg_k.strip()] = pkg_v.strip()
                idx += 2
            elif not tok.startswith('-'):
                target_dir = (caller_dir / tok).resolve()
                idx += 1
            else:
                idx += 1

        try:
            return run_hostutils(
                target_dir,
                auto_patch=auto_patch,
                dry_run=dry_run,
                set_versions=set_versions,
            )
        except HostingError as error:
            print(f'Error en hostutils: {error}', file=sys.stderr)
            return 1

    print(f'Error: Opcion desconocida para build: {" ".join(tokens)}', file=sys.stderr)
    print(_build_help(), file=sys.stderr)
    return 2


def main(*args):
    argv = list(args[0])
    if not argv:
        print(_main_help())
        return 0

    if argv[0] in {'--version', '-V'}:
        print(f'Bagron {BAGRON_VERSION}')
        return 0

    if argv[0] in {'-h', '--help'}:
        print(_main_help())
        return 0

    if argv[0] in {'--vscode', 'vscode'}:
        return _vscode_command(argv)

    if argv[0] in {'library', 'inspect', 'verify', 'unpack', 'sign'}:
        return _library_command(argv)

    if argv[0] == 'install':
        return _install_command(argv)

    if argv[0] == 'build':
        return _build_command(argv)

    if argv[0] == '--hostutils':
        return _build_command(['build', *argv])

    strict_ownership = '--strict-ownership' in argv
    argv = [arg for arg in argv if arg != '--strict-ownership']
    source, output_path, execute, parse_error = _parse_compile_args(argv)
    if parse_error:
        print(parse_error, file=sys.stderr)
        print(_main_help(), file=sys.stderr)
        return 2

    caller_dir = Path(os.environ.get('BAGRON_CALLER_DIR', os.getcwd())).resolve()
    target_path = Path(source)
    if not target_path.is_absolute():
        target_path = (caller_dir / target_path).resolve()

    compiler = Compiler()
    compiler.strict_ownership = strict_ownership
    try:
        artifacts = compiler.compile(target_path)
    except CompilationError as error:
        print(f'Compilation failed: {error}', file=sys.stderr)
        return 1

    for warning in compiler.warnings:
        print(f'Warning: {warning}', file=sys.stderr)

    final_executable = artifacts.executable
    if output_path is not None:
        out_target = Path(output_path)
        if not out_target.is_absolute():
            out_target = (caller_dir / out_target).resolve()
        out_target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(artifacts.executable, out_target)
            final_executable = out_target
        except OSError as error:
            print(f'Error al generar archivo de salida {out_target}: {error}', file=sys.stderr)
            return 1

    print(final_executable)

    if execute:
        if str(getattr(compiler.storage, 'system', '')).lower() == 'android':
            print(
                'Execution failed: no se puede ejecutar un binario Android '
                'cruzado directamente en este host; usa adb para desplegarlo.',
                file=sys.stderr,
            )
            return 1
        try:
            process = subprocess.run([str(final_executable)], cwd=str(caller_dir))
            return process.returncode
        except Exception as error:
            print(f'Execution failed: {error}', file=sys.stderr)
            return 1

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
