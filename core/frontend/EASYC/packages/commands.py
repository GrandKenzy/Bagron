"""Comandos `egl pack install|uninstall|list`: gestión de librerías (.lib.egl) en EGLLibs."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from core.packages import bundle, layout

USAGE = (
    "Uso:\n"
    "  egl pack install [ruta] [--tar <target>] [-y|--force]\n"
    "  egl pack uninstall [--tar <target>] <Nombre>\n"
    "  egl pack list [--tar <target>]\n"
    "\n"
    "Sin --tar la librería usa el Target de su main.egl y se instala en EGLLibs/libraries.\n"
    "Con --tar 'egl-c' se instala en EGLLibs/backends/c/libraries."
)


def _project_name(source_path: str | Path) -> str:
    p = Path(source_path).resolve()
    if p.is_file():
        p = p.parent
    return p.parent.name if p.name == "source" else p.name


def _confirm(question: str) -> bool:
    if not sys.stdin or not sys.stdin.isatty():
        return False
    try:
        return input(f"{question} [s/N]: ").strip().lower() in ("s", "si", "sí", "y", "yes")
    except EOFError:
        return False


def pack_install(source_path: str | Path = ".", target: str | None = None, force: bool = False) -> int:
    from core.compiler import compile_project

    name = _project_name(source_path)
    backend = layout.normalize_backend(target) if target else None
    dest = layout.installed_library_path(name, backend)
    scope = f"backends/{backend}/libraries" if backend else "libraries"

    if dest.exists():
        print(f"[EGL Pack] Aviso: ya existe una librería '{name}' en EGLLibs/{scope}.", flush=True)
        if not force and not _confirm("¿Deseas reemplazarla?"):
            print("[EGL Pack] Instalación cancelada (usa -y/--force para reemplazar sin preguntar).", flush=True)
            return 1

    layout.ensure_layout(backend)
    tmp = layout.temp_dir() / f"{name}{layout.LIB_EXT}"
    tmp.unlink(missing_ok=True)

    print(f"[EGL Pack] Empaquetando '{name}' desde '{source_path}'...", flush=True)
    compile_project(
        source_path,
        output_file=tmp,
        is_library=True,
        target_override=layout.target_name(backend) if backend else None,
    )

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tmp), str(dest))
    bundle.clear_components_cache(name, backend or "c")
    print(f"[EGL Pack] Librería '{name}' instalada en: {dest}", flush=True)
    return 0


def pack_uninstall(name: str, target: str | None = None) -> int:
    backend = layout.normalize_backend(target) if target else None
    clean = name[: -len(layout.LIB_EXT)] if name.endswith(layout.LIB_EXT) else name
    dest = layout.installed_library_path(clean, backend)
    scope = f"backends/{backend}/libraries" if backend else "libraries"
    if not dest.is_file():
        print(f"[EGL Pack Error] La librería '{clean}' no está instalada en EGLLibs/{scope}.", flush=True)
        return 1
    dest.unlink()
    for b in ([backend] if backend else _all_backends()):
        bundle.clear_components_cache(clean, b)
    print(f"[EGL Pack] Librería '{clean}' desinstalada de EGLLibs/{scope}.", flush=True)
    return 0


def pack_list(target: str | None = None) -> int:
    backend = layout.normalize_backend(target) if target else None
    base = layout.backend_libraries_dir(backend) if backend else layout.libraries_dir()
    libs = sorted(p.name[: -len(layout.LIB_EXT)] for p in base.glob(f"*{layout.LIB_EXT}")) if base.is_dir() else []
    print(f"[EGL Pack] Librerías en {base}:" if libs else f"[EGL Pack] Sin librerías en {base}.", flush=True)
    for n in libs:
        print(f"  - {n}")
    return 0


def _all_backends() -> list[str]:
    root = layout.get_egllibs_dir() / layout.BACKENDS
    return [p.name for p in root.iterdir() if p.is_dir()] if root.is_dir() else []


def pack_main(args: list[str]) -> int:
    """Punto de entrada del comando `egl pack ...` (args sin el 'pack')."""
    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        return 0 if args else 1

    action = args[0].lower()
    target: str | None = None
    force = False
    positional: list[str] = []
    i = 1
    while i < len(args):
        a = args[i]
        if a in ("--tar", "--target", "-t"):
            if i + 1 >= len(args):
                print("Error: --tar requiere un valor (ej: --tar \"egl-c\").")
                return 1
            target = args[i + 1]
            i += 2
            continue
        if a in ("-y", "--yes", "--force", "-f"):
            force = True
        else:
            positional.append(a)
        i += 1

    try:
        if action == "install":
            return pack_install(positional[0] if positional else ".", target, force)
        if action in ("uninstall", "remove"):
            if not positional:
                print("Error: indica el nombre de la librería. Uso: egl pack uninstall --tar \"egl-c\" \"MyLib\"")
                return 1
            return pack_uninstall(positional[0], target)
        if action == "list":
            return pack_list(target)
    except Exception as e:
        print(f"[EGL Pack Error] {e}", flush=True)
        return 1

    print(f"Error: Subcomando desconocido '{action}'.\n{USAGE}")
    return 1
