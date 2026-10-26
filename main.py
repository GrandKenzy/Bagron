import sys

from core.compiler import Compiler


def main(*args):
    argv = args[0]
    if not argv:
        print("Uso: vnma run main.py <archivo.bg>")
        return
    compiler = Compiler()
    target = argv[1] if len(argv) > 1 else argv[0]
    compiler.compile(target)


if __name__ == '__main__':
    main(sys.argv[1:])
