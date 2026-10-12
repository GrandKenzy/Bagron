import sys
import os
import shutil
import zipfile
import json
import urllib.request
import subprocess
from pathlib import Path

GITHUB_REPO = "GrandKenzy/EGL"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
LATEST_RELEASE_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

def get_install_root() -> Path:
    return Path(__file__).resolve().parent.parent

def get_github_auth_header() -> dict[str, str]:
    headers = {"User-Agent": "EGL-Updater", "Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        try:
            p = subprocess.Popen(['git', 'credential', 'fill'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            out, _ = p.communicate('protocol=https\nhost=github.com\n\n')
            for line in out.splitlines():
                if line.startswith('password='):
                    token = line.split('=', 1)[1].strip()
                    break
        except Exception:
            pass
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

def parse_semver(v_str: str) -> tuple[int, ...]:
    clean = v_str.strip().lstrip('v').lstrip('V')
    parts = []
    for p in clean.split('.'):
        digits = ''.join(c for c in p if c.isdigit())
        if digits:
            parts.append(int(digits))
        else:
            parts.append(0)
    return tuple(parts)

def fetch_latest_release_info() -> dict | None:
    try:
        req = urllib.request.Request(LATEST_RELEASE_API_URL, headers=get_github_auth_header())
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # Si no hay releases marcados como 'latest', consultar la lista general
            try:
                req2 = urllib.request.Request(RELEASES_API_URL, headers=get_github_auth_header())
                with urllib.request.urlopen(req2, timeout=10) as resp2:
                    releases = json.loads(resp2.read().decode())
                    if releases and isinstance(releases, list):
                        return releases[0]
            except Exception:
                pass
        return None
    except Exception:
        return None

def check_for_updates() -> tuple[bool, str, dict | None]:
    from core.cli import VERSION
    current = VERSION
    latest_info = fetch_latest_release_info()
    if not latest_info:
        return False, current, None
    tag = latest_info.get("tag_name", "").lstrip("v")
    curr_v = parse_semver(current)
    tag_v = parse_semver(tag)
    has_newer = tag_v > curr_v
    return has_newer, tag, latest_info

def update_egl(force: bool = False) -> bool:
    from core.cli import VERSION
    print(f"[EGL Update] Comprobando actualizaciones para EGL en GitHub ({GITHUB_REPO})...", flush=True)

    root_dir = get_install_root()
    is_git_repo = (root_dir / '.git').is_dir() and shutil.which('git') is not None

    has_newer, latest_tag, release_info = check_for_updates()

    if not force and not has_newer:
        if release_info:
            print(f"[EGL Update] EGL ya se encuentra actualizado en la version mas reciente (v{VERSION}).", flush=True)
        else:
            print(f"[EGL Update] No se encontraron versiones publicadas mas recientes que v{VERSION}.", flush=True)
            if is_git_repo:
                print("[EGL Update] Actualizando repositorio local con git pull...", flush=True)
                res = subprocess.run(['git', 'pull'], cwd=str(root_dir))
                if res.returncode == 0:
                    print("[EGL Update] ¡Repositorio sincronizado exitosamente!", flush=True)
                    return True
        return True

    print(f"[EGL Update] ¡Nueva version disponible! v{VERSION} -> v{latest_tag}", flush=True)
    if release_info and release_info.get("body"):
        print(f"--- Novedades de la version v{latest_tag} ---")
        print(release_info.get("body"))
        print("---------------------------------------------")

    if is_git_repo:
        print("[EGL Update] Repositorio Git detectado. Sincronizando con git fetch y pull...", flush=True)
        try:
            subprocess.run(['git', 'fetch', '--tags'], cwd=str(root_dir), check=True)
            subprocess.run(['git', 'pull', 'origin', 'main'], cwd=str(root_dir), check=True)
            print(f"[EGL Update] ¡EGL actualizado con exito via Git a la version v{latest_tag}!", flush=True)
            return True
        except Exception as e:
            print(f"[EGL Update] Git pull no pudo completarse ({e}). Intentando descarga directa...", flush=True)

    # Descarga directa de Release o ZIP del tag
    download_url = None
    if release_info and release_info.get("zipball_url"):
        download_url = release_info.get("zipball_url")
    if not download_url:
        download_url = f"https://github.com/{GITHUB_REPO}/archive/refs/tags/v{latest_tag}.zip"

    try:
        print(f"[EGL Update] Descargando actualizacion desde: {download_url}...", flush=True)
        temp_zip = root_dir / '_update_temp.zip'
        req = urllib.request.Request(download_url, headers=get_github_auth_header())
        with urllib.request.urlopen(req) as resp, open(temp_zip, 'wb') as f:
            total_size = resp.headers.get('content-length')
            downloaded = 0
            while True:
                chunk = resp.read(16384)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total_size:
                    pct = int((downloaded / int(total_size)) * 100)
                    print(f"\r[EGL Update] Descargado: {pct}% ({downloaded // 1024} KB)", end='', flush=True)
            print()

        print("[EGL Update] Aplicando archivos actualizados...", flush=True)
        extract_dir = root_dir / '_update_extracted'
        if extract_dir.exists():
            shutil.rmtree(extract_dir, ignore_errors=True)

        with zipfile.ZipFile(temp_zip, 'r') as zf:
            zf.extractall(extract_dir)

        # Localizar carpeta interna del zip
        content_root = None
        for p in extract_dir.iterdir():
            if p.is_dir() and (p / 'egl.py').is_file():
                content_root = p
                break

        if not content_root:
            content_root = extract_dir

        # Copiar archivos esenciales (core, tools, source, egl.py)
        for item in ['core', 'tools', 'egl.py', 'README.md']:
            src = content_root / item
            dst = root_dir / item
            if src.is_file():
                shutil.copy2(src, dst)
            elif src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(src, dst)

        # EGLLibs se fusiona (no se borra) para conservar las librerías instaladas por el usuario
        egllibs_src = content_root / 'EGLLibs'
        if egllibs_src.is_dir():
            shutil.copytree(egllibs_src, root_dir / 'EGLLibs', dirs_exist_ok=True)

        # Limpiar temporales
        if temp_zip.exists():
            temp_zip.unlink()
        if extract_dir.exists():
            shutil.rmtree(extract_dir, ignore_errors=True)

        # Actualizar Gram si es necesario
        try:
            from tools.install import install_gram
            install_gram()
        except Exception:
            pass

        print(f"[EGL Update] ¡EGL se ha actualizado exitosamente a la version v{latest_tag}!", flush=True)
        return True
    except Exception as e:
        print(f"[EGL Update Error] No se pudo completar la actualizacion: {e}", flush=True)
        return False
