import sys
import shutil
import zipfile
import subprocess
import urllib.request
from pathlib import Path

GRAM_REPO_URL = "https://github.com/GrandKenzy/Gram.git"
GRAM_ZIP_URL = "https://github.com/GrandKenzy/Gram/archive/refs/heads/main.zip"

def get_private_vendor_dir() -> Path:
    base_dir = Path(__file__).resolve().parent.parent
    return base_dir / '.egl' / 'vendor'

def safe_rmtree(path: Path):
    import stat
    def on_error(func, p, exc_info):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass
    if path.exists():
        shutil.rmtree(path, onerror=on_error)

def install_gram(target_dir: Path | None = None) -> bool:
    if target_dir is None:
        target_dir = get_private_vendor_dir() / 'Gram'

    target_dir = Path(target_dir).resolve()
    print(f"[EGL] Instalando librería 'gram' en entorno privado: '{target_dir}'...", flush=True)

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    success = False

    # 1. Intentar actualizar o clonar mediante git si está disponible
    git_bin = shutil.which('git')
    if git_bin:
        try:
            if (target_dir / '.git').is_dir():
                print("[EGL] Repositorio Git detectado en vendor. Actualizando con git pull...", flush=True)
                res = subprocess.run([git_bin, '-C', str(target_dir), 'pull'], capture_output=True, text=True)
                if res.returncode == 0 and (target_dir / 'gram').is_dir():
                    success = True
            if not success:
                print("[EGL] Clonando repositorio público desde GitHub con Git...", flush=True)
                safe_rmtree(target_dir)
                res = subprocess.run([git_bin, 'clone', '--depth', '1', GRAM_REPO_URL, str(target_dir)], capture_output=True, text=True)
                if res.returncode == 0 and (target_dir / 'gram').is_dir():
                    success = True
                else:
                    print("[EGL] Git clone no completó, usando descarga directa de archivo ZIP...", flush=True)
        except Exception:
            pass

    # 2. Si no hay git o falló, descargar el ZIP de la rama main
    if not success:
        try:
            print(f"[EGL] Descargando código fuente desde GitHub ({GRAM_ZIP_URL})...", flush=True)
            zip_dest = target_dir.parent / '_gram_temp.zip'
            req = urllib.request.Request(GRAM_ZIP_URL, headers={'User-Agent': 'EasyC-EGL-Installer'})
            with urllib.request.urlopen(req) as resp, open(zip_dest, 'wb') as out_f:
                total_len = resp.headers.get('content-length')
                downloaded = 0
                while True:
                    chunk = resp.read(16384)
                    if not chunk:
                        break
                    out_f.write(chunk)
                    downloaded += len(chunk)
                    if total_len:
                        pct = int((downloaded / int(total_len)) * 100)
                        print(f"\r[EGL] Descarga: {pct}% ({downloaded // 1024} KB)", end='', flush=True)
                print()

            print("[EGL] Descomprimiendo en entorno privado...", flush=True)
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)

            temp_extract = target_dir.parent / '_temp_gram_extract'
            if temp_extract.exists():
                shutil.rmtree(temp_extract, ignore_errors=True)

            with zipfile.ZipFile(zip_dest, 'r') as zf:
                zf.extractall(temp_extract)

            # GitHub empaqueta la rama en la subcarpeta Gram-main
            found = None
            for p in temp_extract.iterdir():
                if p.is_dir() and (p / 'gram').is_dir():
                    found = p
                    break

            if found:
                safe_rmtree(target_dir)
                shutil.move(str(found), str(target_dir))
                success = True

            if zip_dest.exists():
                zip_dest.unlink()
            if temp_extract.exists():
                shutil.rmtree(temp_extract, ignore_errors=True)
        except Exception as e:
            print(f"[EGL Error] Error al descargar 'gram': {e}", flush=True)
            return False

    if success and (target_dir / 'gram').is_dir():
        if str(target_dir) not in sys.path:
            sys.path.insert(0, str(target_dir))
        try:
            import gram
            print(f"[EGL] ¡Librería 'gram' instalada y verificada exitosamente en el entorno privado!", flush=True)
            print(f"[EGL] Ubicación privada: '{target_dir}' (sin alterar tu entorno Python global).", flush=True)
            return True
        except ImportError as err:
            print(f"[EGL Error] 'gram' se extrajo pero falló al importarse: {err}", flush=True)
            return False
    else:
        print("[EGL Error] No se pudo encontrar el paquete 'gram' tras la descarga.", flush=True)
        return False
