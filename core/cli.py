import sys
import subprocess
import shutil
from pathlib import Path
from core.compiler import compile_project
from core.externs.manager import manager

VERSION = "0.2.0"

def clear_cache(root_dir: Path | None = None) -> int:
    if root_dir is None:
        root_dir = Path(__file__).resolve().parent.parent
    deleted = 0
    for p in list(root_dir.rglob('*')):
        if not p.exists():
            continue
        if p.is_dir() and p.name in ('__pycache__', '.cache', '.pytest_cache'):
            shutil.rmtree(p, ignore_errors=True)
            deleted += 1
        elif p.is_file() and p.suffix in ('.pyc', '.pyo'):
            try:
                p.unlink()
                deleted += 1
            except Exception:
                pass
    return deleted

def print_help():
    print("Easy-C (EGL) Compiler CLI")
    print("Uso:")
    print("  egl compile [ruta] [-o <salida.c>] [--library] [--build] [--run] [--cc <compilador>] [-l <lib>] [-I <dir>] [-L <dir>]")
    print("  egl run [ruta] [-o <salida.c>] [--cc <compilador>] [-l <lib>] [-I <dir>] [-L <dir>]")
    print("  egl update [--force]")
    print("  egl download <gcc|msvc>")
    print("  egl install gram")
    print("  egl cache clear")
    print("  egl extension [--install] [-o <ruta.vsix>]")
    print("  egl --version")
    print("  egl --help")
    print("")
    print("Comandos:")
    print("  compile [ruta]     Compila un proyecto EGL con 'main.egl' (por defecto 'source' o '.').")
    print("  run [ruta]         Compila, construye el ejecutable y lo ejecuta directamente.")
    print("  update             Comprueba y actualiza Easy-C a la versión más reciente en GitHub.")
    print("  download <target>  Descarga/detecta un compilador C nativo (gcc o msvc) para Backend C.")
    print("  install gram       Instala la librería 'gram' en un entorno privado y aislado (.egl/vendor).")
    print("  cache clear        Elimina archivos y directorios de caché (.cache, __pycache__, .pyc).")
    print("  extension          Genera la extensión oficial de VS Code (.vsix) con sintaxis y tema Noble Dark.")
    print("                     Usa '--install' para instalarla directamente en Visual Studio Code.")
    print("")
    print("Opciones:")
    print("  -b, --build      Construye el ejecutable binario delegando al backend del target.")
    print("  -r, --run        Construye el ejecutable y lo ejecuta inmediatamente.")
    print("  -o, --output     Nombre del archivo C monolítico generado (default: program.c).")
    print("  --library        Compila el proyecto como una librería empaquetada (.lib.egl).")
    print("  --cc             Compilador nativo a utilizar (gcc, clang, cl, msvc, tcc).")
    print("  -l, --link       Enlaza una librería externa (ej: -l SDL3).")
    print("  -I, --include    Agrega una carpeta de cabeceras al compilador.")
    print("  -L, --lib-dir    Agrega una carpeta de librerías al linker.")
    print("  --force          Fuerza la reinstalación/actualización en 'egl update'.")
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

    if command == 'update':
        force = '--force' in args[1:] or '-f' in args[1:]
        from core.update import update_easy_c
        ok = update_easy_c(force=force)
        return 0 if ok else 1

    if command == 'install':
        sub = args[1].lower() if len(args) > 1 else ''
        if sub == 'gram':
            from core.install import install_gram
            ok = install_gram()
            return 0 if ok else 1
        else:
            print(f"Error: Paquete desconocido '{sub}'. Uso: egl install gram")
            return 1

    if command in ('download', 'toolchain'):
        target = args[1].lower() if len(args) > 1 else ''
        if not target:
            print("Error: Debes especificar el compilador a descargar (gcc o msvc). Uso: egl download <gcc|msvc>")
            return 1
        backend_name = manager.get_backend()
        try:
            import importlib
            backend_mod = importlib.import_module(f'core.backend.{backend_name}.download')
            download_fn = getattr(backend_mod, 'download_compiler', None)
        except Exception:
            download_fn = None

        if not download_fn:
            from core.backend.c.download import download_compiler
            download_fn = download_compiler

        ok = download_fn(target)
        return 0 if ok else 1

    if command in ('cache', 'clean'):
        sub = args[1].lower() if len(args) > 1 else ''
        if command == 'clean' or sub in ('clear', 'clean', ''):
            print("[EGL] Limpiando archivos de caché...", flush=True)
            total = clear_cache()
            print(f"[EGL] Caché eliminada exitosamente ({total} directorios/archivos eliminados).", flush=True)
            return 0
        else:
            print(f"Error: Subcomando desconocido para cache '{sub}'. Usa 'egl cache clear'.")
            return 1

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
    is_library = False
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
        elif arg in ('--library', '-lib'):
            is_library = True
            i += 1
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

    if is_library:
        if output_file == 'program.c':
            p_src = Path(source_path).resolve()
            lib_base = p_src.name if p_src.name not in ('source', '.', '') else p_src.parent.name
            output_file = f'{lib_base}.lib.egl'
        elif not output_file.endswith('.lib.egl'):
            if output_file.endswith('.c'):
                output_file = output_file[:-2] + '.lib.egl'
            else:
                output_file = output_file + '.lib.egl'

    try:
        print(f"[EGL] Compilando proyecto en: '{source_path}'", flush=True)
        out_path = compile_project(source_path, output_file=output_file, is_library=is_library)
        if is_library:
            print(f"[EGL] Librería empaquetada exitosamente: '{out_path.name}'", flush=True)
            return 0
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
            backend_name = manager.get_backend()
            try:
                import importlib
                backend_mod = importlib.import_module(f'core.backend.{backend_name}')
            except ImportError as err:
                raise RuntimeError(f"No se pudo cargar el backend '{backend_name}' para la compilación binaria: {err}")

            if not hasattr(backend_mod, 'compile'):
                raise NotImplementedError(f"El backend '{backend_name}' no implementa la función 'compile' para generar ejecutables binarios.")

            res_code, exe_name = backend_mod.compile(
                source_file=out_path,
                output_file=out_path.with_suffix('.exe' if sys.platform == 'win32' else ''),
                compiler=cc,
                include_dirs=all_includes,
                lib_dirs=all_lib_dirs,
                link_libraries=all_links,
                bin_files=conventions.get('bin_files', [])
            )
            if res_code != 0:
                return res_code

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
