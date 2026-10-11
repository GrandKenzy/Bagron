import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.installer_core import install_easy_c, uninstall_easy_c

def main():
    args = sys.argv[1:]
    target_dir = None
    force_embed_python = False
    force_cli = False

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ('--target', '-t') and i + 1 < len(args):
            target_dir = Path(args[i + 1])
            i += 2
        elif arg in ('--embed-python', '--standalone'):
            force_embed_python = True
            i += 1
        elif arg in ('--cli', '-c'):
            force_cli = True
            i += 1
        elif arg in ('--uninstall', '-u'):
            uninstall_easy_c(target_dir)
            return 0
        elif arg in ('-h', '--help'):
            print("Instalador de Easy-C (EGL)")
            print("Uso:")
            print("  easy-c-installer.exe [opciones]")
            print("  python installer.py [opciones]")
            print("")
            print("Opciones:")
            print("  --cli, -c          Ejecuta la instalacion directamente en consola (sin interfaz gráfica).")
            print("  --target, -t       Ruta de instalacion personalizada (por defecto: %LOCALAPPDATA%\\Programs\\Easy-C).")
            print("  --embed-python     Descarga e instala Python 3.13 embebido aun si ya existe en el sistema.")
            print("  --uninstall, -u    Desinstala Easy-C y lo remueve del PATH.")
            print("  --help, -h         Muestra este mensaje.")
            return 0
        else:
            i += 1

    # Si no se forzó modo consola y no se pasaron rutas manuales, intentar lanzar la interfaz gráfica (HTML/CSS/JS)
    if not force_cli and target_dir is None:
        try:
            from tools.installer_gui import run_gui, HAS_WEBVIEW
            if HAS_WEBVIEW:
                return run_gui()
        except Exception as e:
            print(f"[Installer Warning] No se pudo iniciar la interfaz grafica ({e}). Usando modo consola...")

    ok = install_easy_c(target_dir=target_dir, force_embed_python=force_embed_python, source_root=ROOT_DIR)
    return 0 if ok else 1

if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    sys.exit(main())
