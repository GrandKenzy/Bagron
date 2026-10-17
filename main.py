import sys

from core.compiler import compile


def main(*args):
    argv = args[0]
    if not argv:
        print("Uso: vnma run main.py <archivo.egl>")
        return
    compile(argv[1])


if __name__ == '__main__':
    main(sys.argv[1:])
    
    
    
    