import sys

if sys.version_info < (3, 13):
    sys.exit("Error: Easy-C (EGL) requiere Python 3.13 o superior debido al uso de sintaxis avanzada (PEP 701 f-strings).")

from pathlib import Path

# 1. Registrar entorno privado de dependencias (.egl/vendor) para no manchar el entorno global
ROOT_DIR = Path(__file__).resolve().parent
PRIVATE_VENDOR_PATHS = [
    ROOT_DIR / 'vendor',
    ROOT_DIR / 'vendor' / 'Gram',
    ROOT_DIR / '.egl' / 'vendor',
    ROOT_DIR / '.egl' / 'vendor' / 'Gram',
    Path.home() / '.egl' / 'vendor',
    Path.home() / '.egl' / 'vendor' / 'Gram',
]
for vp in PRIVATE_VENDOR_PATHS:
    if vp.is_dir() and str(vp) not in sys.path:
        sys.path.insert(0, str(vp))

# 2. Detección de la librería requerida 'gram'
try:
    import gram
    HAS_GRAM = True
except ImportError:
    HAS_GRAM = False

if not HAS_GRAM:
    args = sys.argv[1:]
    if args and args[0].lower() == 'install' and len(args) > 1 and args[1].lower() == 'gram':
        from core.install import install_gram
        sys.exit(0 if install_gram() else 1)
    elif args and args[0].lower() in ('download', 'toolchain'):
        from core.backend.c.download import download_compiler
        target = args[1].lower() if len(args) > 1 else ''
        if not target:
            print("Error: Debes especificar el compilador a descargar (gcc o msvc). Uso: egl download <gcc|msvc>")
            sys.exit(1)
        sys.exit(0 if download_compiler(target) else 1)
    else:
        print("[EGL Error] La librería requerida 'gram' no está instalada en el entorno.")
        print("Para instalarla de forma aislada en un entorno privado sin afectar tu sistema, ejecuta:")
        print("    python egl.py install gram   (o egl install gram)")
        sys.exit(1)

from core.cli import main

if __name__ == '__main__':
    sys.exit(main())

