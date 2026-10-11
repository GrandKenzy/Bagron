import sys
import os
import shutil
import zipfile
import urllib.request
import subprocess
import ctypes
from pathlib import Path

# Protección contra OSError [Errno 22] Invalid argument en ejecutables GUI de Windows
class SafeWriter:
    def __init__(self, original):
        self.original = original
    def write(self, s):
        try:
            if self.original:
                return self.original.write(s)
        except Exception:
            pass
    def flush(self):
        try:
            if self.original:
                return self.original.flush()
        except Exception:
            pass

try:
    if sys.stdout is None or not hasattr(sys.stdout, 'write'):
        sys.stdout = SafeWriter(None)
    else:
        sys.stdout = SafeWriter(sys.stdout)
    if sys.stderr is None or not hasattr(sys.stderr, 'write'):
        sys.stderr = SafeWriter(None)
    else:
        sys.stderr = SafeWriter(sys.stderr)
except Exception:
    pass

PYTHON_EMBED_URL = "https://www.python.org/ftp/python/3.13.2/python-3.13.2-embed-amd64.zip"

def get_default_install_dir() -> Path:
    local_app_data = os.environ.get('LOCALAPPDATA')
    if local_app_data:
        return Path(local_app_data) / 'Programs' / 'Easy-C'
    return Path.home() / 'AppData' / 'Local' / 'Programs' / 'Easy-C'

def is_python_313_or_higher(py_executable: str | None = None) -> bool:
    cmd = [py_executable or sys.executable, '-c', 'import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)']
    try:
        res = subprocess.run(cmd, capture_output=True)
        return res.returncode == 0
    except Exception:
        return False

def add_to_user_path(bin_dir: Path) -> bool:
    if sys.platform != 'win32':
        return False
    bin_str = str(bin_dir.resolve())
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_ALL_ACCESS)
        try:
            curr_path, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            curr_path = ""

        paths = [p.strip() for p in curr_path.split(';') if p.strip()]
        if any(p.lower() == bin_str.lower() for p in paths):
            print(f"[Installer] La ruta '{bin_str}' ya se encuentra registrada en el PATH del usuario.", flush=True)
            winreg.CloseKey(key)
            return True

        paths.append(bin_str)
        new_path = ';'.join(paths)
        winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
        winreg.CloseKey(key)

        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        result = ctypes.c_ulong()
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment",
            SMTO_ABORTIFHUNG, 5000, ctypes.byref(result)
        )
        print(f"[Installer] ¡Directorio añadido exitosamente al PATH del usuario! ('{bin_str}')", flush=True)
        return True
    except Exception as e:
        print(f"[Installer Error] No se pudo actualizar el PATH del registro: {e}", flush=True)
        return False

def remove_from_user_path(bin_dir: Path) -> bool:
    if sys.platform != 'win32':
        return False
    bin_str = str(bin_dir.resolve()).lower()
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_ALL_ACCESS)
        try:
            curr_path, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            return True

        paths = [p.strip() for p in curr_path.split(';') if p.strip()]
        new_paths = [p for p in paths if p.lower() != bin_str]
        new_path = ';'.join(new_paths)
        winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
        winreg.CloseKey(key)

        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        result = ctypes.c_ulong()
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment",
            SMTO_ABORTIFHUNG, 5000, ctypes.byref(result)
        )
        print(f"[Installer] Ruta removida del PATH del usuario.", flush=True)
        return True
    except Exception as e:
        print(f"[Installer Error] No se pudo remover del PATH: {e}", flush=True)
        return False

def download_embedded_python(dest_dir: Path) -> bool:
    dest_dir.mkdir(parents=True, exist_ok=True)
    python_exe = dest_dir / 'python.exe'
    if python_exe.is_file():
        print(f"[Installer] Python embebido ya presente en: '{dest_dir}'", flush=True)
        return True

    print(f"[Installer] Descargando entorno portable de Python 3.13 desde python.org...", flush=True)
    zip_dest = dest_dir.parent / '_py_embed_temp.zip'
    try:
        req = urllib.request.Request(PYTHON_EMBED_URL, headers={'User-Agent': 'EasyC-Installer'})
        with urllib.request.urlopen(req) as resp, open(zip_dest, 'wb') as f:
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
                    print(f"\r[Installer] Descarga de Python 3.13: {pct}% ({downloaded // 1024} KB)", end='', flush=True)
            print()

        print("[Installer] Extrayendo entorno de Python...", flush=True)
        with zipfile.ZipFile(zip_dest, 'r') as zf:
            zf.extractall(dest_dir)

        if zip_dest.exists():
            zip_dest.unlink()

        pth_files = list(dest_dir.glob('*._pth'))
        if pth_files:
            pth_file = pth_files[0]
            content = pth_file.read_text(encoding='utf-8')
            extra_lines = "\n.\n..\n../vendor\n../vendor/Gram\nimport site\n"
            pth_file.write_text(content + extra_lines, encoding='utf-8')

        print(f"[Installer] ¡Python 3.13 portable configurado exitosamente en: '{dest_dir}'!", flush=True)
        return True
    except Exception as e:
        print(f"[Installer Error] Error al descargar/configurar Python embebido: {e}", flush=True)
        return False

def compile_launcher_binary(source_c: Path, output_exe: Path) -> bool:
    gcc_bin = shutil.which('gcc')
    if gcc_bin:
        try:
            cmd = [gcc_bin, '-O2', '-municode', str(source_c), '-o', str(output_exe)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and output_exe.is_file():
                return True
        except Exception:
            pass

    cl_bin = shutil.which('cl')
    if cl_bin:
        try:
            cmd = [cl_bin, '/O2', str(source_c), f'/Fe:{output_exe}']
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and output_exe.is_file():
                return True
        except Exception:
            pass
    return False

def install_easy_c(target_dir: Path | None = None, force_embed_python: bool = False, source_root: Path | None = None) -> bool:
    if target_dir is None:
        target_dir = get_default_install_dir()

    target_dir = Path(target_dir).resolve()
    print("==========================================================")
    print("           Easy-C (EGL) - Instalador del Sistema          ")
    print("==========================================================")
    print(f"[Installer] Directorio de destino: '{target_dir}'", flush=True)

    if source_root is None:
        source_root = Path(__file__).resolve().parent.parent

    # 1. Crear estructura organizada de carpetas
    bin_dir = target_dir / 'bin'
    core_dir = target_dir / 'core'
    lib_dir = target_dir / 'libraries'
    src_dir = target_dir / 'source'
    vendor_dir = target_dir / 'vendor'
    python_dir = target_dir / 'python'

    for d in [bin_dir, core_dir, lib_dir, src_dir, vendor_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 2. Copiar archivos del compilador
    print("[Installer] Instalando componentes y modulos del compilador...", flush=True)
    for folder_name in ['core', 'libraries', 'source']:
        src = source_root / folder_name
        dst = target_dir / folder_name
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)

    for single_file in ['egl.py', 'README.md', 'LICENSE']:
        src = source_root / single_file
        if src.is_file():
            shutil.copy2(src, target_dir / single_file)

    # 3. Comprobar / Instalar Python 3.13 si no existe o si se solicita
    need_embed_python = force_embed_python or not is_python_313_or_higher()
    if need_embed_python:
        print("[Installer] El sistema no cuenta con Python 3.13+ o se requiere entorno autonomo.", flush=True)
        ok = download_embedded_python(python_dir)
        if not ok:
            print("[Installer Warning] No se pudo instalar Python portable. Asegurate de tener Python 3.13 instalado globalmente.")
    else:
        print("[Installer] Python 3.13+ detectado en el sistema.", flush=True)

    # 4. Asegurar presencia de 'gram' en el vendor privado
    target_gram = vendor_dir / 'Gram'
    local_gram = source_root / '.egl' / 'vendor' / 'Gram'
    if local_gram.is_dir() and not target_gram.is_dir():
        print("[Installer] Copiando libreria privada 'gram' al directorio vendor...", flush=True)
        shutil.copytree(local_gram, target_gram)
    elif not (target_gram / 'gram').is_dir():
        print("[Installer] Descargando libreria 'gram' en el entorno vendor privado...", flush=True)
        try:
            from core.install import install_gram
            install_gram(target_gram)
        except Exception:
            # Fallback descarga directa
            try:
                import urllib.request
                GRAM_ZIP_URL = "https://github.com/GrandKenzy/Gram/archive/refs/heads/main.zip"
                z_tmp = target_dir / '_gram_tmp.zip'
                urllib.request.urlretrieve(GRAM_ZIP_URL, z_tmp)
                with zipfile.ZipFile(z_tmp, 'r') as zf:
                    zf.extractall(target_dir / '_gram_unzip')
                for p in (target_dir / '_gram_unzip').iterdir():
                    if p.is_dir() and (p / 'gram').is_dir():
                        shutil.move(str(p), str(target_gram))
                        break
                if z_tmp.exists(): z_tmp.unlink()
                if (target_dir / '_gram_unzip').exists(): shutil.rmtree(target_dir / '_gram_unzip', ignore_errors=True)
            except Exception as e_gram:
                print(f"[Installer Warning] No se pudo descargar 'gram': {e_gram}")

    # 5. Generar y colocar ejecutable nativo egl.exe en bin/
    print("[Installer] Generando ejecutables del compilador en bin/...", flush=True)
    launcher_c = source_root / 'tools' / 'launcher.c'
    target_exe = bin_dir / 'egl.exe'
    built_exe = False

    if launcher_c.is_file():
        built_exe = compile_launcher_binary(launcher_c, target_exe)

    if not built_exe:
        tools_exe = source_root / 'tools' / 'egl.exe'
        if tools_exe.is_file():
            shutil.copy2(tools_exe, target_exe)
            built_exe = True

    target_cmd = bin_dir / 'egl.cmd'
    cmd_content = (
        "@echo off\r\n"
        "setlocal\r\n"
        "set \"ROOT=%~dp0..\"\r\n"
        "if exist \"%ROOT%\\python\\python.exe\" (\r\n"
        "    \"%ROOT%\\python\\python.exe\" \"%ROOT%\\egl.py\" %*\r\n"
        ") else (\r\n"
        "    python \"%ROOT%\\egl.py\" %*\r\n"
        ")\r\n"
    )
    target_cmd.write_text(cmd_content, encoding='utf-8')

    # 6. Registrar en el PATH del usuario
    print("[Installer] Registrando Easy-C en el PATH del sistema...", flush=True)
    add_to_user_path(bin_dir)

    print("==========================================================")
    print("      ¡Easy-C (EGL) se ha instalado correctamente!        ")
    print("==========================================================")
    print(f"Ubicacion: {target_dir}")
    print(f"Ejecutable: {target_exe if built_exe else target_cmd}")
    print("\nYa puedes abrir una nueva terminal y ejecutar:")
    print("    egl --version")
    print("    egl run main.egl")
    print("    egl update")
    print("==========================================================")
    return True

def uninstall_easy_c(target_dir: Path | None = None) -> bool:
    if target_dir is None:
        target_dir = get_default_install_dir()
    target_dir = Path(target_dir).resolve()
    print(f"[Installer] Desinstalando Easy-C de: '{target_dir}'...", flush=True)
    remove_from_user_path(target_dir / 'bin')
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    print("[Installer] Easy-C desinstalado correctamente.", flush=True)
    return True
