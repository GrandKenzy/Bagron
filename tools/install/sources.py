"""Descarga de los archivos fuente de EGL cuando no están disponibles localmente."""
from __future__ import annotations

import shutil
import urllib.request
import zipfile
from pathlib import Path

from tools import config
from tools.install.console import log
from tools.install.paths import get_cache_dir


def _has_sources(root: Path) -> bool:
    return (root / "core").is_dir() and (root / config.ENTRY_SCRIPT).is_file()


def _download_archive(zip_dest: Path) -> bool:
    for url in config.SOURCE_ARCHIVE_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
            with urllib.request.urlopen(req, timeout=config.SOURCE_DOWNLOAD_TIMEOUT) as resp, open(zip_dest, "wb") as f:
                shutil.copyfileobj(resp, f)
            return True
        except Exception:
            continue
    return False


def _merge_into_cache(found: Path, cache_dir: Path) -> None:
    for item in found.iterdir():
        dst = cache_dir / item.name
        if dst.exists():
            if dst.is_dir():
                shutil.rmtree(dst, ignore_errors=True)
            else:
                dst.unlink()
        shutil.move(str(item), str(dst))


def ensure_source_files(source_root: Path, notify_cb=None) -> Path:
    """Garantiza core/, egl.py, etc.; si faltan, los descarga de GitHub a una caché."""
    if _has_sources(source_root):
        return source_root

    cache_dir = get_cache_dir()
    if _has_sources(cache_dir):
        return cache_dir

    msg = f"Descargando componentes de {config.APP_NAME} desde GitHub..."
    log(msg)
    if notify_cb:
        notify_cb(msg)

    cache_dir.mkdir(parents=True, exist_ok=True)
    zip_dest = cache_dir / "_src.zip"
    if not _download_archive(zip_dest) or not zip_dest.is_file():
        return source_root

    unzip_dir = cache_dir / "_unzip"
    shutil.rmtree(unzip_dir, ignore_errors=True)
    try:
        with zipfile.ZipFile(zip_dest, "r") as zf:
            zf.extractall(unzip_dir)
        zip_dest.unlink(missing_ok=True)
        found = next((p for p in unzip_dir.iterdir() if p.is_dir() and (p / "core").is_dir()), None)
        if found:
            _merge_into_cache(found, cache_dir)
            shutil.rmtree(unzip_dir, ignore_errors=True)
            return cache_dir
    except Exception:
        pass
    return source_root
