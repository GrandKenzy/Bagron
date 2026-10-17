"""Orquestador de la instalación y desinstalación de EGL."""
from __future__ import annotations

import shutil
from pathlib import Path

from tools import config
from tools.config import InstallOptions
from tools.install.console import ProgressCallback, install_safe_streams, log, report
from tools.install.deploy import copy_components
from tools.install.launcher import build_launcher
from tools.install.paths import InstallLayout, get_default_install_dir, get_source_root
from tools.install.pythonenv import download_embedded_python, is_python_313_or_higher
from tools.install.sources import ensure_source_files
from tools.install.winpath import (
    add_to_user_path,
    register_windows_uninstaller,
    remove_from_user_path,
    unregister_windows_uninstaller,
)

_BANNER = "=" * 58


def _print_header(target_dir: Path) -> None:
    print(_BANNER)
    print(f"           {config.APP_NAME} - Instalador del Sistema          ")
    print(_BANNER)
    log(f"Directorio de destino: '{target_dir}'")


def _print_footer(layout: InstallLayout, built_exe: bool) -> None:
    print(_BANNER)
    print(f"      ¡{config.APP_NAME} se ha instalado correctamente!        ")
    print(_BANNER)
    print(f"Ubicacion: {layout.root}")
    print(f"Ejecutable: {layout.exe if built_exe else layout.cmd}")
    print("\nYa puedes abrir una nueva terminal y ejecutar:")
    print("    egl --version")
    print("    egl run main.egl")
    print(_BANNER)


def _step_python(layout: InstallLayout, force_embed: bool, progress: ProgressCallback | None) -> None:
    if force_embed or not is_python_313_or_higher():
        report(progress, 45, "Descargando entorno Python 3.13 portable...",
               "El sistema no cuenta con Python 3.13+ o se requiere entorno autonomo.")

        def on_download(pct: int, msg: str) -> None:
            if progress:
                progress(45 + int(pct * 0.2), "Descargando Python 3.13...", msg)

        if download_embedded_python(layout.python, progress_cb=on_download):
            report(progress, 65, "Python 3.13 configurado.", f"Entorno portable en: {layout.python}")
        else:
            log("No se pudo instalar Python portable. Asegurate de tener Python 3.13 instalado globalmente.",
                tag="Installer Warning")
    else:
        report(progress, 55, "Python del sistema verificado.", "Python 3.13+ detectado.")


def run_install(options: InstallOptions, progress: ProgressCallback | None = None) -> bool:
    install_safe_streams()
    layout = InstallLayout(options.target_dir or get_default_install_dir())
    _print_header(layout.root)

    report(progress, 10, "Creando carpetas estructuradas...", f"Directorio destino: {layout.root}")
    source_root = ensure_source_files(
        options.source_root or get_source_root(),
        lambda msg: progress and progress(15, "Descargando componentes...", msg),
    )
    layout.create()

    report(progress, 35, "Copiando componentes del compilador...", "Instalando componentes y modulos del compilador...")
    copy_components(source_root, layout.root)

    _step_python(layout, options.force_embed_python, progress)

    report(progress, 80, "Generando lanzador nativo bin/egl.exe...", "Generando ejecutables del compilador en bin/...")
    built_exe = build_launcher(source_root, layout)

    if options.add_to_path:
        report(progress, 95, "Registrando en PATH del usuario...", f"Registrando {config.APP_NAME} en el PATH del sistema...")
        add_to_user_path(layout.bin)

    register_windows_uninstaller(layout.root, layout.uninstaller_cmd)

    report(progress, 100, "¡Instalación completada con éxito!", f"{config.APP_NAME} instalado en: {layout.root}")
    _print_footer(layout, built_exe)
    return True


def install_egl(
    target_dir: Path | None = None,
    force_embed_python: bool = False,
    source_root: Path | None = None,
    add_to_path: bool = True,
    progress: ProgressCallback | None = None,
) -> bool:
    return run_install(
        InstallOptions(
            target_dir=target_dir,
            force_embed_python=force_embed_python,
            add_to_path=add_to_path,
            source_root=source_root,
        ),
        progress,
    )


def uninstall_egl(target_dir: Path | None = None) -> bool:
    from tools.uninstaller import run_uninstallation
    install_safe_streams()
    layout = InstallLayout(target_dir or get_default_install_dir())
    return run_uninstallation(layout.root)
