"""Instalación de la librería privada 'gram' (git clone o descarga ZIP)."""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

from tools import config
from tools.install.paths import find_local_gram, get_private_vendor_dir

TAG = "EGL"


def _log(msg: str) -> None:
    print(f"[{TAG}] {msg}", flush=True)


def safe_rmtree(path: Path) -> None:
    def on_error(func, p, exc_info):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass
    if path.exists():
        shutil.rmtree(path, onerror=on_error)


def _has_package(target_dir: Path) -> bool:
    return (target_dir / config.GRAM_PACKAGE).is_dir()


def _install_with_git(target_dir: Path) -> bool:
    git_bin = shutil.which("git")
    if not git_bin:
        return False
    try:
        if (target_dir / ".git").is_dir():
            _log("Repositorio Git detectado en vendor. Actualizando con git pull...")
            res = subprocess.run([git_bin, "-C", str(target_dir), "pull"], capture_output=True, text=True)
            if res.returncode == 0 and _has_package(target_dir):
                return True
        _log("Clonando repositorio público desde GitHub con Git...")
        safe_rmtree(target_dir)
        res = subprocess.run(
            [git_bin, "clone", "--depth", "1", config.GRAM_REPO_URL, str(target_dir)],
            capture_output=True, text=True,
        )
        if res.returncode == 0 and _has_package(target_dir):
            return True
        _log("Git clone no completó, usando descarga directa de archivo ZIP...")
    except Exception:
        pass
    return False


def _download_zip(zip_dest: Path) -> None:
    req = urllib.request.Request(config.GRAM_ZIP_URL, headers={"User-Agent": config.USER_AGENT})
    with urllib.request.urlopen(req) as resp, open(zip_dest, "wb") as out_f:
        total_len = resp.headers.get("content-length")
        downloaded = 0
        while True:
            chunk = resp.read(config.GRAM_DOWNLOAD_CHUNK)
            if not chunk:
                break
            out_f.write(chunk)
            downloaded += len(chunk)
            if total_len:
                pct = int(downloaded / int(total_len) * 100)
                print(f"\r[{TAG}] Descarga: {pct}% ({downloaded // 1024} KB)", end="", flush=True)
        print()


def _install_with_zip(target_dir: Path) -> bool:
    _log(f"Descargando código fuente desde GitHub ({config.GRAM_ZIP_URL})...")
    zip_dest = target_dir.parent / config.GRAM_ZIP_TEMP
    temp_extract = target_dir.parent / config.GRAM_EXTRACT_TEMP
    _download_zip(zip_dest)

    _log("Descomprimiendo en entorno privado...")
    shutil.rmtree(target_dir, ignore_errors=True)
    shutil.rmtree(temp_extract, ignore_errors=True)
    with zipfile.ZipFile(zip_dest, "r") as zf:
        zf.extractall(temp_extract)

    success = False
    found = next((p for p in temp_extract.iterdir() if p.is_dir() and _has_package(p)), None)
    if found:
        safe_rmtree(target_dir)
        shutil.move(str(found), str(target_dir))
        success = True

    zip_dest.unlink(missing_ok=True)
    shutil.rmtree(temp_extract, ignore_errors=True)
    return success


def install_gram(target_dir: Path | None = None) -> bool:
    if target_dir is None:
        target_dir = get_private_vendor_dir() / config.GRAM_DIRNAME
    target_dir = Path(target_dir).resolve()
    _log(f"Instalando librería 'gram' en entorno privado: '{target_dir}'...")
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    success = _install_with_git(target_dir)
    if not success:
        try:
            success = _install_with_zip(target_dir)
        except Exception as e:
            print(f"[{TAG} Error] Error al descargar 'gram': {e}", flush=True)
            return False

    if success and _has_package(target_dir):
        if str(target_dir) not in sys.path:
            sys.path.insert(0, str(target_dir))
        try:
            import gram  # noqa: F401
            _log("¡Librería 'gram' instalada y verificada exitosamente en el entorno privado!")
            _log(f"Ubicación privada: '{target_dir}' (sin alterar tu entorno Python global).")
            return True
        except ImportError as err:
            print(f"[{TAG} Error] 'gram' se extrajo pero falló al importarse: {err}", flush=True)
            return False
    print(f"[{TAG} Error] No se pudo encontrar el paquete 'gram' tras la descarga.", flush=True)
    return False


def deploy_gram(source_root: Path, target_gram: Path) -> None:
    """Copia Gram desde el código fuente al vendor de la instalación, o lo descarga."""
    local_gram = find_local_gram(source_root)
    if local_gram and not target_gram.is_dir():
        shutil.copytree(local_gram, target_gram)
    elif not _has_package(target_gram):
        try:
            install_gram(target_gram)
        except Exception:
            pass
