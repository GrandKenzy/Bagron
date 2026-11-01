import sys

from core.compiler import CompilationError, Compiler


def main(*args):
    argv = list(args[0])
    if not argv:
        print(
            'Uso: vnma run main.py [--aot] [--aot-strict] '
            '[--aot-parser <ejecutable>] <archivo.bg>'
        )
        return

    positional: list[str] = []
    aot = False
    aot_strict = False
    aot_parser = None
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument == '--aot':
            aot = True
        elif argument == '--aot-strict':
            aot = True
            aot_strict = True
        elif argument == '--aot-parser':
            index += 1
            if index >= len(argv):
                print('--aot-parser requiere una ruta', file=sys.stderr)
                return 2
            aot_parser = argv[index]
        elif argument in {'-h', '--help'}:
            print(
                'Uso: vnma run main.py [--aot] [--aot-strict] '
                '[--aot-parser <ejecutable>] <archivo.bg>'
            )
            return 0
        else:
            positional.append(argument)
        index += 1

    if not positional:
        print('Falta el archivo .bg', file=sys.stderr)
        return 2

    compiler = Compiler(
        aot=aot,
        aot_parser=aot_parser,
        aot_strict=aot_strict,
    )
    target = positional[0]
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
