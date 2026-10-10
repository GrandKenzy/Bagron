import sys
import subprocess
from pathlib import Path
from core.compiler import compile_project

VERSION = "0.2.0"

def print_help():
    print("Easy-C (EGL) Compiler CLI")
    print("Uso:")
    print("  egl compile [ruta] [-o <salida.c>] [--run] [--cc <compilador>]")
    print("  egl run [ruta] [-o <salida.c>] [--cc <compilador>]")
    print("  egl --version")
    print("  egl --help")
    print("")
    print("Comandos:")
    print("  compile [ruta]   Compila un proyecto EGL con 'main.egl' (por defecto 'source' o '.').")
    print("  run [ruta]       Compila y ejecuta el proyecto directamente.")
    print("")
    print("Opciones:")
    print("  -r, --run        Compila el archivo C generado con GCC y lo ejecuta inmediatamente.")
    print("  -o, --output     Nombre del archivo C monolítico generado (default: program.c).")
    print("  --cc             Compilador de C a utilizar para --run (default: gcc).")
    print("  -v, --version    Muestra la versión de EGL.")
    print("  -h, --help       Muestra este mensaje de ayuda.")

def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]

    if not args or '-h' in args or '--help' in args:
        print_help()
        return 0

    if '-v' in args or '--version' in args:
        print(f"EGL Compiler v{VERSION}")
        return 0

    command = args[0]
    do_run = False
    start_idx = 1

    if command in ('compile', 'build'):
        start_idx = 1
    elif command == 'run':
        do_run = True
        start_idx = 1
    elif command in ('-r', '--run'):
        do_run = True
        start_idx = 0
    elif not command.startswith('-'):
        start_idx = 0
    else:
        print(f"Error: Comando desconocido '{command}'. Usa 'egl --help' para ver los comandos disponibles.")
        return 1

    source_path = None
    output_file = 'program.c'
    cc = 'gcc'

    i = start_idx
    while i < len(args):
        arg = args[i]
        if arg in ('-o', '--output', '--out'):
            if i + 1 < len(args):
                output_file = args[i + 1]
                i += 2
                continue
            else:
                print("Error: Se requiere una ruta para la opción -o.")
                return 1
        elif arg in ('-r', '--run'):
            do_run = True
            i += 1
        elif arg == '--cc':
            if i + 1 < len(args):
                cc = args[i + 1]
                i += 2
                continue
            else:
                print("Error: Se requiere el nombre del compilador para --cc.")
                return 1
        elif not arg.startswith('-') and source_path is None:
            source_path = arg
            i += 1
        else:
            i += 1

    if source_path is None:
        if Path('source/main.egl').is_file():
            source_path = 'source'
        elif Path('main.egl').is_file():
            source_path = '.'
        else:
            print("Error: Falta la ruta del proyecto. Uso: egl compile [ruta] [--run]")
            return 1

    try:
        print(f"[EGL] Compilando proyecto en: '{source_path}'", flush=True)
        out_path = compile_project(source_path, output_file=output_file)
        print(f"[EGL] Archivo monolítico generado exitosamente: '{out_path.name}'", flush=True)

        if do_run:
            exe_name = out_path.with_suffix('.exe' if sys.platform == 'win32' else '')
            print(f"[EGL] Compilando con {cc}: '{exe_name.name}'...", flush=True)
            compile_cmd = [cc, str(out_path), '-o', str(exe_name)]
            res = subprocess.run(compile_cmd)
            if res.returncode != 0:
                print(f"[EGL] Error en la compilación con {cc}.", flush=True)
                return res.returncode
            print(f"[EGL] Ejecutando: '{exe_name.name}'\n--- Salida del programa ---", flush=True)
            run_res = subprocess.run([str(exe_name)])
            print("---------------------------", flush=True)
            return run_res.returncode

        return 0
    except Exception as e:
        print(f"[EGL Error] {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
