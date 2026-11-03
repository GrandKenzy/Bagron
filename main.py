import sys
import json

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
        print(
            'Uso: vnma run main.py <archivo.bg>\n'
            'El frontend Gram FFI produce GIR; semántica y backend LLVM '
            'siguen en Bagron.'
        )
        return

    if argv[0] in {'-h', '--help'}:
        print(
            'Uso: vnma run main.py <archivo.bg>\n'
            + _library_help() + '\n'
            'El frontend Gram FFI produce GIR; semántica y backend LLVM '
            'siguen en Bagron.'
        )
        return 0
    if argv[0] in {'library', 'inspect', 'verify', 'unpack'}:
        return _library_command(argv)
    if len(argv) != 1:
        print('Uso: vnma run main.py <archivo.bg>', file=sys.stderr)
        return 2
    if argv[0].startswith('-'):
        print(
            'No se admiten opciones de parser: Bagron requiere el frontend Gram FFI.',
            file=sys.stderr,
        )
        return 2

    compiler = Compiler()
    target = argv[0]
    try:
        artifacts = compiler.compile(target)
    except CompilationError as error:
        print(f'Compilation failed: {error}', file=sys.stderr)
        return 1
    for warning in compiler.warnings:
        print(f'Warning: {warning}', file=sys.stderr)
    print(artifacts.executable)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
