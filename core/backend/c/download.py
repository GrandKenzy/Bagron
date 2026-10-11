import sys
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

def get_toolchains_dir() -> Path:
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    return base_dir / '.egl' / 'toolchains'

def find_portable_gcc() -> Path | None:
    candidates = [
        get_toolchains_dir() / 'gcc' / 'bin' / 'gcc.exe',
        get_toolchains_dir() / 'mingw64' / 'bin' / 'gcc.exe',
        get_toolchains_dir() / 'w64devkit' / 'bin' / 'gcc.exe',
        Path.home() / '.egl' / 'toolchains' / 'gcc' / 'bin' / 'gcc.exe',
        Path.home() / '.egl' / 'toolchains' / 'mingw64' / 'bin' / 'gcc.exe',
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None

def download_gcc() -> bool:
    print("[Backend C] Verificando compilador GCC...", flush=True)
    existing = shutil.which('gcc')
    if existing:
        print(f"[Backend C] GCC ya se encuentra disponible en el sistema: '{existing}'", flush=True)
        try:
            res = subprocess.run([existing, '--version'], capture_output=True, text=True)
            first_line = res.stdout.splitlines()[0] if res.stdout else ''
            print(f"[Backend C] {first_line}", flush=True)
        except Exception:
            pass
        return True

    portable = find_portable_gcc()
    if portable:
        print(f"[Backend C] Compilador GCC portable detectado en: '{portable}'", flush=True)
        return True

    if sys.platform == 'win32':
        winget_bin = shutil.which('winget')
        if winget_bin:
            print("[Backend C] Instalando GCC (WinLibs MinGW-w64) mediante winget...", flush=True)
            cmd = [
                winget_bin, 'install', '-e', '--id', 'BrechtSanders.WinLibs.POSIX.UCRT',
                '--accept-source-agreements', '--accept-package-agreements'
            ]
            try:
                res = subprocess.run(cmd)
                if res.returncode == 0:
                    print("[Backend C] ¡GCC instalado exitosamente mediante winget! (Reinicia la consola si es necesario para actualizar el PATH)", flush=True)
                    return True
            except Exception as e:
                print(f"[Backend C] Error ejecutando winget: {e}", flush=True)

        print("[Backend C] Puedes instalar GCC en Windows ejecutando:")
        print("    winget install BrechtSanders.WinLibs.POSIX.UCRT")
        print("O descargando MinGW-w64 manualmente desde https://winlibs.com")
        return False
    elif sys.platform == 'darwin':
        print("[Backend C] En macOS, instalando Command Line Tools de Xcode...", flush=True)
        subprocess.run(['xcode-select', '--install'])
        return True
    else:
        print("[Backend C] En Linux, instala GCC mediante el gestor de paquetes del sistema:")
        print("    Ubuntu/Debian: sudo apt update && sudo apt install -y build-essential")
        print("    Fedora/RHEL:   sudo dnf install -y gcc")
        print("    Arch Linux:    sudo pacman -S gcc")
        return False

def download_msvc() -> bool:
    print("[Backend C] Verificando compilador MSVC (cl.exe)...", flush=True)
    existing = shutil.which('cl')
    if existing:
        print(f"[Backend C] MSVC ya se encuentra disponible en el entorno: '{existing}'", flush=True)
        return True

    if sys.platform != 'win32':
        print("[Backend C Error] MSVC (Microsoft Visual C++) solo está disponible en Windows.", flush=True)
        return False

    winget_bin = shutil.which('winget')
    if winget_bin:
        print("[Backend C] Descargando e instalando Visual Studio Build Tools (MSVC)...", flush=True)
        print("[Backend C] Esto puede tardar varios minutos dependiendo de la conexión a Internet.", flush=True)
        cmd = [
            winget_bin, 'install', '-e', '--id', 'Microsoft.VisualStudio.2022.BuildTools',
            '--override', '--passive --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended',
            '--accept-source-agreements', '--accept-package-agreements'
        ]
        try:
            res = subprocess.run(cmd)
            if res.returncode == 0:
                print("[Backend C] ¡Visual Studio Build Tools (MSVC) instalado exitosamente!", flush=True)
                return True
            else:
                print(f"[Backend C] winget terminó con código {res.returncode}.", flush=True)
        except Exception as e:
            print(f"[Backend C Error] Falló winget: {e}", flush=True)

    try:
        vs_url = "https://aka.ms/vs/17/release/vs_BuildTools.exe"
        installer_path = Path.home() / 'Downloads' / 'vs_BuildTools.exe'
        installer_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"[Backend C] Descargando instalador oficial de Microsoft desde {vs_url}...", flush=True)
        urllib.request.urlretrieve(vs_url, installer_path)
        print(f"[Backend C] Instalador descargado en: '{installer_path}'. Iniciando instalación...", flush=True)
        subprocess.Popen([str(installer_path)])
        print("[Backend C] Selecciona la carga de trabajo 'Desarrollo para el escritorio con C++' en el instalador para completar.", flush=True)
        return True
    except Exception as e:
        print(f"[Backend C Error] No se pudo descargar el instalador de MSVC: {e}", flush=True)
        return False

def download_compiler(compiler_name: str) -> bool:
    name = compiler_name.lower().strip()
    if name in ('gcc', 'mingw', 'gnu'):
        return download_gcc()
    elif name in ('msvc', 'cl', 'visualstudio', 'vs'):
        return download_msvc()
    else:
        print(f"[Backend C Error] Compilador '{compiler_name}' no soportado. Opciones disponibles: gcc, msvc.")
        return False
