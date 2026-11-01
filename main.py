import sys

from core.compiler import CompilationError, Compiler


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
            'El frontend Gram FFI produce GIR; semántica y backend LLVM '
            'siguen en Bagron.'
        )
        return 0
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
