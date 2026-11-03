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
from core.library import (
    LibraryError,
    inspect_library,
    pack_compiled_library,
    pack_library,
    unpack_library,
    verify_library,
)


def _library_help() -> str:
    return (
        'Uso:\n'
        '  vnma run main.py library --v1 <source> -o <archivo.lib> [--name N] [--version V]\n'
        '  vnma run main.py library --v2 <source> -o <archivo.lib> [--name N] [--version V]\n'
        '  vnma run main.py inspect <archivo.lib>\n'
        '  vnma run main.py verify <archivo.lib>\n'
        '  vnma run main.py unpack <archivo.lib> <destino>'
    )


def _main_help() -> str:
    return (
        'Uso:\n'
        '  Bagron <archivo.bg> [-o <salida.exe>] [--execute]\n'
        '  vnma run main.py <archivo.bg> [-o <salida.exe>] [--execute]\n\n'
        'Comandos de librería:\n'
        + _library_help() + '\n\n'
        'El frontend Gram FFI produce GIR; semántica y backend LLVM siguen en Bagron.'
    )


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
    try:
        if command == 'library':
            selected = [flag for flag in ('--v1', '--v2') if flag in argv]
            if len(selected) != 1:
                print(_library_help(), file=sys.stderr)
                return 2
            version_flag = selected[0]
            source_index = argv.index(version_flag) + 1
            if source_index >= len(argv) or '-o' not in argv:
                print(_library_help(), file=sys.stderr)
                return 2
            source = argv[source_index]
            output = argv[argv.index('-o') + 1]
            name = None
            version = '0.1.0'
            index = 2
            while index < len(argv):
                if argv[index] == '--name' and index + 1 < len(argv):
                    name = argv[index + 1]
                    index += 2
                    continue
                if argv[index] == '--version' and index + 1 < len(argv):
                    version = argv[index + 1]
                    index += 2
                    continue
                index += 1
            packer = pack_compiled_library if version_flag == '--v2' else pack_library
            result = packer(source, output, name=name, version=version)
            print(result)
            return 0
        if command == 'inspect' and len(argv) == 2:
            print(json.dumps(
                inspect_library(argv[1]),
                ensure_ascii=False,
                indent=2,
            ))
            return 0
        if command == 'verify' and len(argv) == 2:
            package = verify_library(argv[1])
            print(f'OK {package.name} v{package.library_version} {package.package_id}')
            return 0
        if command == 'unpack' and len(argv) == 3:
            print(unpack_library(argv[1], argv[2]))
            return 0
    except LibraryError as error:
        print(f'Library failed: {error}', file=sys.stderr)
        return 1
    print(_library_help(), file=sys.stderr)
    return 2


def main(*args):
    argv = list(args[0])
    if not argv:
        print(_main_help())
        return 0

    if argv[0] in {'-h', '--help'}:
        print(_main_help())
        return 0

    if argv[0] in {'library', 'inspect', 'verify', 'unpack'}:
        return _library_command(argv)

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
        try:
            process = subprocess.run([str(final_executable)], cwd=str(caller_dir))
            return process.returncode
        except Exception as error:
            print(f'Execution failed: {error}', file=sys.stderr)
            return 1

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
