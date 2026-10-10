import sys
import subprocess
import shutil
from pathlib import Path
from core.compiler import compile_project
from core.externs.manager import manager

VERSION = "0.2.0"

def print_help():
    print("Easy-C (EGL) Compiler CLI")
    print("Uso:")
    print("  egl compile [ruta] [-o <salida.c>] [--build] [--run] [--cc <compilador>] [-l <lib>] [-I <dir>] [-L <dir>]")
    print("  egl run [ruta] [-o <salida.c>] [--cc <compilador>] [-l <lib>] [-I <dir>] [-L <dir>]")
    print("  egl extension [--install] [-o <ruta.vsix>]")
    print("  egl --version")
    print("  egl --help")
    print("")
    print("Comandos:")
    print("  compile [ruta]   Compila un proyecto EGL con 'main.egl' (por defecto 'source' o '.').")
    print("  run [ruta]       Compila, construye el ejecutable y lo ejecuta directamente.")
    print("  extension        Genera la extensión oficial de VS Code (.vsix) con sintaxis y tema Noble Dark.")
    print("                   Usa '--install' para instalarla directamente en Visual Studio Code.")
    print("")
    print("Opciones:")
    print("  -b, --build      Compila el archivo C generado con GCC para producir el ejecutable.")
    print("  -r, --run        Compila con GCC y ejecuta el programa inmediatamente.")
    print("  -o, --output     Nombre del archivo C monolítico generado (default: program.c).")
    print("  --cc             Compilador de C a utilizar (default: gcc).")
    print("  -l, --link       Enlaza una librería externa con el compilador C (ej: -l SDL3).")
    print("  -I, --include    Agrega una carpeta de cabeceras C al compilador.")
    print("  -L, --lib-dir    Agrega una carpeta de librerías al linker.")
    print("  --install        Instala automáticamente el paquete .vsix en VS Code.")
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
    do_build = False
    start_idx = 1

    if command in ('extension', 'vsix', 'syntax'):
        do_install = '--install' in args[1:] or '-i' in args[1:]
        out_vsix = None
        i = 1
        while i < len(args):
            if args[i] in ('-o', '--output') and i + 1 < len(args):
                out_vsix = args[i + 1]
                i += 2
            else:
                i += 1
        from core.extension import compile_extension, install_extension
        print("[EGL] Empaquetando extensión de VS Code para Easy-C...", flush=True)
        vsix_file = compile_extension(out_vsix)
        print(f"[EGL] Extensión VSIX generada exitosamente en: '{vsix_file}'", flush=True)
        if do_install:
            print("[EGL] Instalando extensión en Visual Studio Code...", flush=True)
            ok, msg = install_extension(vsix_file)
            print(f"[EGL] {msg}", flush=True)
            return 0 if ok else 1
        return 0

    if command in ('compile', 'build'):
        start_idx = 1
        if command == 'build':
            do_build = True
    elif command == 'run':
        do_run = True
        do_build = True
        start_idx = 1
    elif command in ('-r', '--run'):
        do_run = True
        do_build = True
        start_idx = 0
    elif command in ('-b', '--build'):
        do_build = True
        start_idx = 0
    elif not command.startswith('-'):
        start_idx = 0
    else:
        print(f"Error: Comando desconocido '{command}'. Usa 'egl --help' para ver los comandos disponibles.")
        return 1

    source_path = None
    output_file = 'program.c'
    cc = 'gcc'
    cli_links: list[str] = []
    cli_includes: list[Path] = []
    cli_lib_dirs: list[Path] = []

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
            do_build = True
            i += 1
        elif arg in ('-b', '--build'):
            do_build = True
            i += 1
        elif arg == '--cc':
            if i + 1 < len(args):
                cc = args[i + 1]
                i += 2
                continue
            else:
                print("Error: Se requiere el nombre del compilador para --cc.")
                return 1
        elif arg.startswith('-l') and len(arg) > 2:
            cli_links.append(arg[2:])
            i += 1
        elif arg in ('-l', '--link'):
            if i + 1 < len(args):
                cli_links.append(args[i + 1])
                i += 2
                continue
            else:
                print("Error: Se requiere el nombre de la librería para -l/--link.")
                return 1
        elif arg.startswith('-I') and len(arg) > 2:
            cli_includes.append(Path(arg[2:]).resolve())
            i += 1
        elif arg in ('-I', '--include'):
            if i + 1 < len(args):
                cli_includes.append(Path(args[i + 1]).resolve())
                i += 2
                continue
            else:
                print("Error: Se requiere la ruta del directorio para -I/--include.")
                return 1
        elif arg.startswith('-L') and len(arg) > 2:
            cli_lib_dirs.append(Path(arg[2:]).resolve())
            i += 1
        elif arg in ('-L', '--lib-dir'):
            if i + 1 < len(args):
                cli_lib_dirs.append(Path(args[i + 1]).resolve())
                i += 2
                continue
            else:
                print("Error: Se requiere la ruta del directorio para -L/--lib-dir.")
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

        conventions = manager.collect_target_conventions()

        all_includes = list(conventions.get('include_dirs', []))
        for inc in cli_includes:
            if inc not in all_includes:
                all_includes.append(inc)

        all_lib_dirs = list(conventions.get('lib_dirs', []))
        for ld in cli_lib_dirs:
            if ld not in all_lib_dirs:
                all_lib_dirs.append(ld)

        all_links = list(conventions.get('link_flags', []))
        for lk in cli_links:
            if lk not in all_links:
                all_links.append(lk)

        if do_build or do_run:
            exe_name = out_path.with_suffix('.exe' if sys.platform == 'win32' else '')
            print(f"[EGL] Compilando con {cc}: '{exe_name.name}'...", flush=True)
            compile_cmd = [cc, str(out_path), '-o', str(exe_name)]
            for inc in all_includes:
                compile_cmd.extend(['-I', str(inc)])
            for ld in all_lib_dirs:
                compile_cmd.extend(['-L', str(ld)])
            for lk in all_links:
                flag = lk if lk.startswith('-l') else f'-l{lk}'
                compile_cmd.append(flag)

            res = subprocess.run(compile_cmd)
            if res.returncode != 0:
                print(f"[EGL] Error en la compilación con {cc}.", flush=True)
                return res.returncode

            dest_dir = exe_name.parent
            for bin_item in conventions.get('bin_files', []):
                bin_path = Path(bin_item)
                if not bin_path.is_file():
                    found_cand = None
                    for search_folder in all_lib_dirs + all_includes:
                        c1 = search_folder / bin_path.name
                        if c1.is_file():
                            found_cand = c1
                            break
                        c2 = search_folder.parent / 'bin' / bin_path.name
                        if c2.is_file():
                            found_cand = c2
                            break
                    if found_cand:
                        bin_path = found_cand
                if bin_path.is_file():
                    dest_file = dest_dir / bin_path.name
                    if bin_path.resolve() != dest_file.resolve():
                        shutil.copy2(bin_path, dest_file)
                        print(f"[EGL] Binario desplegado: '{bin_path.name}' -> '{dest_dir.name}'", flush=True)

            if do_run:
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
