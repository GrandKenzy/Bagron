"""Rutas del directorio `EGLLibs/`: destino final de las librerías de EGL.

EGLLibs/
    libraries/            .lib.egl que no requieren un backend específico
    backends/<backend>/
        externs/          firmas externas (.externs.egl)
        includes/         carpetas con cabeceras (.h)
        libraries/        .lib.egl específicos del backend
        bin/              binarios (.dll, .so, .dylib)
        lib/              archivos de enlace (libSDL3.dll.a, cmake/, pkgconfig/...)
    .cache/               caché (p. ej. componentes extraídos de .lib.egl)
    .temp/                temporales

Ubicación: variable de entorno `EGL_LIBS` o `<raíz de EGL>/EGLLibs`.
"""
from __future__ import annotations

import os
from pathlib import Path

# Debe coincidir con tools.config.EGLLIBS_DIRNAME
EGLLIBS_DIRNAME = "EGLLibs"
ENV_VAR = "EGL_LIBS"
LIB_EXT = ".lib.egl"

LIBRARIES = "libraries"
BACKENDS = "backends"
EXTERNS = "externs"
INCLUDES = "includes"
BIN = "bin"
LIB = "lib"
CACHE = ".cache"
TEMP = ".temp"

BACKEND_DIRS = (EXTERNS, INCLUDES, LIBRARIES, BIN, LIB)


def normalize_backend(target: str) -> str:
    """'egl-c' -> 'c'; 'c' -> 'c'."""
    t = str(target).strip().strip("\"'").lower()
    return t[4:] if t.startswith("egl-") else t


def same_target(a: str, b: str) -> bool:
    """Compara targets ignorando comillas, mayúsculas y el prefijo 'egl-'."""
    return normalize_backend(a) == normalize_backend(b)


def target_name(backend: str) -> str:
    """'c' -> 'egl-c'."""
    b = normalize_backend(backend)
    return f"egl-{b}"


def get_egllibs_dir() -> Path:
    env = os.environ.get(ENV_VAR)
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parent.parent.parent / EGLLIBS_DIRNAME


def libraries_dir() -> Path:
    return get_egllibs_dir() / LIBRARIES


def backend_dir(backend: str) -> Path:
    return get_egllibs_dir() / BACKENDS / normalize_backend(backend)


def backend_libraries_dir(backend: str) -> Path:
    return backend_dir(backend) / LIBRARIES


def externs_dir(backend: str) -> Path:
    return backend_dir(backend) / EXTERNS


def includes_dir(backend: str) -> Path:
    return backend_dir(backend) / INCLUDES


def lib_dir(backend: str) -> Path:
    return backend_dir(backend) / LIB


def bin_dir(backend: str) -> Path:
    return backend_dir(backend) / BIN


def cache_dir() -> Path:
    return get_egllibs_dir() / CACHE


def temp_dir() -> Path:
    return get_egllibs_dir() / TEMP


def installed_library_path(name: str, backend: str | None = None) -> Path:
    """Ruta de un .lib.egl instalado (agnóstico si `backend` es None)."""
    base = backend_libraries_dir(backend) if backend else libraries_dir()
    return base / f"{name}{LIB_EXT}"


def ensure_layout(backend: str | None = None) -> None:
    """Crea la estructura base de EGLLibs (y la del backend indicado)."""
    root = get_egllibs_dir()
    for p in (libraries_dir(), cache_dir(), temp_dir()):
        p.mkdir(parents=True, exist_ok=True)
    if backend:
        for sub in BACKEND_DIRS:
            (backend_dir(backend) / sub).mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)
