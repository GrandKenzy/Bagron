"""Componentes que viajan dentro de un .lib.egl (externs, includes, lib, bin).

Dentro del zip se guardan como `backend/<backend>/<tipo>/...`.
Al usar la librería se extraen a `EGLLibs/.cache/libs/<backend>/<nombre>/`.
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from core.packages import layout

# Tipos de componente empaquetables y su carpeta equivalente en un proyecto fuente.
KINDS = (layout.EXTERNS, layout.INCLUDES, layout.LIB, layout.BIN)
ZIP_PREFIX = "backend"
STAMP_FILE = ".stamp"
_IGNORED = ("__pycache__", ".cache", ".git")


def collect_components(*roots: Path) -> dict[str, Path]:
    """Busca carpetas externs/includes/lib/bin en las raíces dadas (la primera que exista gana)."""
    found: dict[str, Path] = {}
    for root in roots:
        for kind in KINDS:
            cand = Path(root) / kind
            if kind not in found and cand.is_dir():
                found[kind] = cand.resolve()
    return found


def write_components(zf: zipfile.ZipFile, components: dict[str, Path], backend: str) -> list[str]:
    """Escribe los componentes en el zip. Devuelve la lista de tipos incluidos."""
    included = []
    for kind, folder in components.items():
        count = 0
        for f in folder.rglob("*"):
            if not f.is_file() or any(part in _IGNORED for part in f.relative_to(folder).parts):
                continue
            arc = Path(ZIP_PREFIX) / layout.normalize_backend(backend) / kind / f.relative_to(folder)
            zf.write(f, arcname=arc.as_posix())
            count += 1
        if count:
            included.append(kind)
    return included


def lib_name_from_path(lib_path: Path) -> str:
    name = Path(lib_path).name
    return name[: -len(layout.LIB_EXT)] if name.endswith(layout.LIB_EXT) else Path(lib_path).stem


def components_cache_dir(lib_path: Path, backend: str) -> Path:
    return layout.cache_dir() / "libs" / layout.normalize_backend(backend) / lib_name_from_path(lib_path)


def _stamp(lib_path: Path) -> str:
    st = Path(lib_path).stat()
    return f"{st.st_mtime_ns}-{st.st_size}"


def extract_components(lib_path: Path, backend: str) -> dict[str, Path]:
    """Extrae los componentes del .lib.egl a la caché (solo si cambió). Devuelve tipo -> carpeta."""
    lib_path = Path(lib_path)
    dest = components_cache_dir(lib_path, backend)
    prefix = f"{ZIP_PREFIX}/{layout.normalize_backend(backend)}/"
    stamp = _stamp(lib_path)
    stamp_file = dest / STAMP_FILE

    with zipfile.ZipFile(lib_path, "r") as zf:
        names = [n for n in zf.namelist() if n.startswith(prefix) and not n.endswith("/")]
        if not names:
            return {}
        if not (stamp_file.is_file() and stamp_file.read_text(encoding="utf-8") == stamp):
            shutil.rmtree(dest, ignore_errors=True)
            dest.mkdir(parents=True, exist_ok=True)
            for n in names:
                target = dest / n[len(prefix):]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(n))
            stamp_file.write_text(stamp, encoding="utf-8")

    return {kind: dest / kind for kind in KINDS if (dest / kind).is_dir()}


def clear_components_cache(name: str, backend: str) -> None:
    shutil.rmtree(
        layout.cache_dir() / "libs" / layout.normalize_backend(backend) / name,
        ignore_errors=True,
    )


def register_components(manager, components: dict[str, Path]) -> None:
    """Registra en el ExternsManager los componentes extraídos de una librería."""
    inc = components.get(layout.INCLUDES)
    if inc and inc not in manager.include_dirs:
        manager.include_dirs.append(inc)
    lib = components.get(layout.LIB)
    if lib and lib not in manager.lib_dirs:
        manager.lib_dirs.append(lib)
    bin_d = components.get(layout.BIN)
    if bin_d:
        for f in sorted(bin_d.glob("*")):
            if f.suffix.lower() in (".dll", ".so", ".dylib") and str(f) not in manager.bin_files:
                manager.bin_files.append(str(f))
    ext = components.get(layout.EXTERNS)
    if ext and ext not in manager.extra_extern_dirs:
        manager.extra_extern_dirs.append(ext)
