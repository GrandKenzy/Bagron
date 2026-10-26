import sys

from core.compiler import CompilationError, Compiler


def main(*args):
    argv = args[0]
    if not argv:
        print("Uso: vnma run main.py <archivo.bg>")
        return
    compiler = Compiler()
    target = argv[1] if len(argv) > 1 else argv[0]
    try:
        artifacts = compiler.compile(target)
    except CompilationError as error:
        print(f'Compilation failed: {error}', file=sys.stderr)
        return 1
    print(artifacts.executable)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
