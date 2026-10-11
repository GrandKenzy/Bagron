import sys
import os
import json
import threading
import subprocess
import shutil
from pathlib import Path

try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False

from tools.installer_core import (
    get_default_install_dir,
    is_python_313_or_higher,
    install_easy_c,
)

HTML_CONTENT = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instalador de Easy-C (EGL)</title>
    <style>
        :root {
            --bg-base: #0d1117;
            --bg-card: #161b22;
            --bg-card-hover: #1f242c;
            --border: #30363d;
            --border-glow: #38bdf8;
            --text-main: #f0f6fc;
            --text-muted: #8b949e;
            --accent: #0284c7;
            --accent-hover: #0369a1;
            --accent-glow: rgba(56, 189, 248, 0.35);
            --green: #238636;
            --green-glow: rgba(46, 160, 67, 0.25);
            --yellow: #d29922;
            --blue: #38bdf8;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            user-select: none;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        body {
            background-color: var(--bg-base);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        header {
            padding: 18px 28px;
            background: linear-gradient(180deg, #161b22 0%, #0d1117 100%);
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo-box {
            width: 38px;
            height: 38px;
            background: linear-gradient(135deg, #0284c7 0%, #6366f1 100%);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 900;
            font-size: 20px;
            color: #ffffff;
            box-shadow: 0 0 15px var(--accent-glow);
        }

        .brand-title h1 {
            font-size: 18px;
            font-weight: 700;
            letter-spacing: -0.3px;
        }

        .brand-title p {
            font-size: 12px;
            color: var(--text-muted);
        }

        .version-badge {
            background: #1f242c;
            border: 1px solid var(--border);
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            color: var(--blue);
        }

        main {
            flex: 1;
            padding: 24px 28px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }

        .view {
            display: none;
            flex-direction: column;
            gap: 18px;
            animation: fadeIn 0.3s ease-out;
        }

        .view.active {
            display: flex;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(6px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .section-title {
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            margin-bottom: -6px;
        }

        .input-group {
            display: flex;
            gap: 10px;
        }

        input[type="text"] {
            flex: 1;
            background: var(--bg-card);
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 10px 14px;
            border-radius: 6px;
            font-size: 13px;
            outline: none;
            transition: all 0.2s;
        }

        input[type="text"]:focus {
            border-color: var(--blue);
            box-shadow: 0 0 0 2px var(--accent-glow);
        }

        .btn {
            background: var(--accent);
            color: #fff;
            border: none;
            padding: 10px 18px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 8px;
            justify-content: center;
        }

        .btn:hover {
            background: var(--accent-hover);
            box-shadow: 0 0 10px var(--accent-glow);
        }

        .btn-secondary {
            background: #21262d;
            border: 1px solid var(--border);
            color: var(--text-main);
        }

        .btn-secondary:hover {
            background: #30363d;
            box-shadow: none;
        }

        .btn-large {
            padding: 14px 24px;
            font-size: 15px;
        }

        .grid-cards {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }

        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 14px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            transition: all 0.2s;
        }

        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .card-title {
            font-size: 13px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .card-desc {
            font-size: 12px;
            color: var(--text-muted);
            line-height: 1.4;
        }

        .badge {
            font-size: 11px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 12px;
        }

        .badge-green {
            background: rgba(46, 160, 67, 0.15);
            color: #3fb950;
            border: 1px solid rgba(46, 160, 67, 0.4);
        }

        .badge-yellow {
            background: rgba(210, 153, 34, 0.15);
            color: #d29922;
            border: 1px solid rgba(210, 153, 34, 0.4);
        }

        .badge-blue {
            background: rgba(56, 189, 248, 0.15);
            color: #38bdf8;
            border: 1px solid rgba(56, 189, 248, 0.4);
        }

        .options-box {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px 16px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .checkbox-label {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 13px;
            cursor: pointer;
        }

        .checkbox-label input {
            width: 16px;
            height: 16px;
            accent-color: var(--accent);
            cursor: pointer;
        }

        /* Progreso */
        .progress-container {
            display: flex;
            flex-direction: column;
            gap: 14px;
            padding: 20px 0;
        }

        .progress-bar-bg {
            background: #21262d;
            height: 10px;
            border-radius: 6px;
            overflow: hidden;
            position: relative;
        }

        .progress-bar-fill {
            height: 100%;
            background: linear-gradient(90deg, #0284c7, #38bdf8);
            width: 0%;
            transition: width 0.3s ease;
            box-shadow: 0 0 10px var(--accent-glow);
        }

        .status-text {
            font-size: 13px;
            color: var(--text-main);
            font-weight: 500;
        }

        .console-box {
            background: #090d12;
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 12px;
            font-family: "Consolas", monospace;
            font-size: 11px;
            color: #a5d6ff;
            height: 150px;
            overflow-y: auto;
            white-space: pre-wrap;
        }

        /* Finalización */
        .success-box {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 30px 10px;
            text-align: center;
            gap: 14px;
        }

        .success-icon {
            width: 60px;
            height: 60px;
            background: rgba(46, 160, 67, 0.2);
            border: 2px solid #3fb950;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 30px;
            color: #3fb950;
        }

        footer {
            padding: 14px 28px;
            background: #0d1117;
            border-top: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
    </style>
</head>
<body>
    <header>
        <div class="brand">
            <div class="logo-box">E</div>
            <div class="brand-title">
                <h1>Easy-C (EGL)</h1>
                <p>Compilador Nativo & DSL para C</p>
            </div>
        </div>
        <div class="version-badge">v0.2.0</div>
    </header>

    <main>
        <!-- VISTA 1: CONFIGURACIÓN -->
        <div id="view-config" class="view active">
            <div class="section-title">Directorio de Instalación</div>
            <div class="input-group">
                <input type="text" id="install-path" spellcheck="false" />
                <button class="btn btn-secondary" onclick="browseFolder()">Examinar...</button>
            </div>

            <div class="section-title">Diagnóstico del Sistema</div>
            <div class="grid-cards">
                <div class="card" id="card-python">
                    <div class="card-header">
                        <span class="card-title">Python 3.13+</span>
                        <span class="badge" id="badge-python">Comprobando...</span>
                    </div>
                    <div class="card-desc" id="desc-python">Analizando entorno local...</div>
                </div>

                <div class="card" id="card-gram">
                    <div class="card-header">
                        <span class="card-title">Librería Gram</span>
                        <span class="badge" id="badge-gram">Comprobando...</span>
                    </div>
                    <div class="card-desc" id="desc-gram">Analizando framework gram...</div>
                </div>

                <div class="card" id="card-compiler">
                    <div class="card-header">
                        <span class="card-title">Compilador C</span>
                        <span class="badge badge-green" id="badge-compiler">GCC Detectado</span>
                    </div>
                    <div class="card-desc" id="desc-compiler">Listo para generar ejecutables binarios.</div>
                </div>

                <div class="card" id="card-launcher">
                    <div class="card-header">
                        <span class="card-title">Lanzador Nativo</span>
                        <span class="badge badge-blue">bin/egl.exe</span>
                    </div>
                    <div class="card-desc">Ejecutable de 0ms de latencia integrado para terminal.</div>
                </div>
            </div>

            <div class="section-title">Opciones Adicionales</div>
            <div class="options-box">
                <label class="checkbox-label">
                    <input type="checkbox" id="opt-path" checked />
                    <span>Registrar Easy-C en la variable de entorno <strong>PATH</strong> (recomendado)</span>
                </label>
                <label class="checkbox-label">
                    <input type="checkbox" id="opt-embed" />
                    <span>Instalar siempre un entorno aislado de Python 3.13 portable (independiente del sistema)</span>
                </label>
            </div>
        </div>

        <!-- VISTA 2: PROGRESO -->
        <div id="view-progress" class="view">
            <div class="progress-container">
                <div style="display: flex; justify-content: space-between;">
                    <span class="status-text" id="progress-stage">Iniciando instalación...</span>
                    <span class="status-text" id="progress-pct" style="font-weight: 700; color: var(--blue);">0%</span>
                </div>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" id="progress-bar"></div>
                </div>
            </div>

            <div class="section-title">Registro de Instalación</div>
            <div class="console-box" id="console-logs"></div>
        </div>

        <!-- VISTA 3: FINALIZADO -->
        <div id="view-success" class="view">
            <div class="success-box">
                <div class="success-icon">✓</div>
                <h2 style="font-size: 20px;">¡Easy-C Instalado con Éxito!</h2>
                <p style="color: var(--text-muted); font-size: 13px; max-width: 450px;">
                    Easy-C ya está listo para usarse. Puedes abrir cualquier consola (PowerShell, CMD, Git Bash) y comenzar a compilar.
                </p>
                <div style="background: #161b22; border: 1px solid var(--border); border-radius: 6px; padding: 12px 18px; font-family: monospace; font-size: 13px; color: #38bdf8;">
                    egl --version<br>
                    egl run main.egl
                </div>
            </div>
        </div>
    </main>

    <footer>
        <button class="btn btn-secondary" id="btn-cancel" onclick="exitApp()">Cancelar</button>
        <div style="display: flex; gap: 10px;">
            <button class="btn btn-large" id="btn-action" onclick="startInstall()">Instalar Easy-C</button>
        </div>
    </footer>

    <script>
        let currentStatus = null;

        window.addEventListener('pywebviewready', function() {
            window.pywebview.api.get_system_status().then(function(status) {
                currentStatus = status;
                document.getElementById('install-path').value = status.default_dir;

                // Python card
                const bPy = document.getElementById('badge-python');
                const dPy = document.getElementById('desc-python');
                if (status.python_ok) {
                    bPy.className = 'badge badge-green';
                    bPy.innerText = 'Detectado';
                    dPy.innerText = status.python_version + ' disponible en el sistema.';
                } else {
                    bPy.className = 'badge badge-yellow';
                    bPy.innerText = 'Auto-Instalar';
                    dPy.innerText = 'Se descargará Python 3.13 portable automáticamente.';
                    document.getElementById('opt-embed').checked = true;
                }

                // Gram card
                const bGram = document.getElementById('badge-gram');
                const dGram = document.getElementById('desc-gram');
                if (status.gram_ok) {
                    bGram.className = 'badge badge-green';
                    bGram.innerText = 'Disponible';
                    dGram.innerText = 'Gram Framework listo en el entorno.';
                } else {
                    bGram.className = 'badge badge-blue';
                    bGram.innerText = 'Auto-Descarga';
                    dGram.innerText = 'Se instalará de forma aislada en vendor/Gram.';
                }

                // Compiler card
                const bComp = document.getElementById('badge-compiler');
                const dComp = document.getElementById('desc-compiler');
                if (status.compiler_name) {
                    bComp.className = 'badge badge-green';
                    bComp.innerText = status.compiler_name.toUpperCase();
                    dComp.innerText = status.compiler_detail;
                } else {
                    bComp.className = 'badge badge-yellow';
                    bComp.innerText = 'Pendiente';
                    dComp.innerText = 'Puedes instalar GCC con egl download gcc.';
                }
            });
        });

        function browseFolder() {
            window.pywebview.api.browse_folder().then(function(folder) {
                if (folder) {
                    document.getElementById('install-path').value = folder;
                }
            });
        }

        function appendLog(line) {
            const c = document.getElementById('console-logs');
            c.innerText += line + '\\n';
            c.scrollTop = c.scrollHeight;
        }

        function startInstall() {
            const targetDir = document.getElementById('install-path').value;
            const addToPath = document.getElementById('opt-path').checked;
            const embedPy = document.getElementById('opt-embed').checked;

            // Cambiar a vista de progreso
            document.getElementById('view-config').classList.remove('active');
            document.getElementById('view-progress').classList.add('active');
            document.getElementById('btn-action').style.display = 'none';
            document.getElementById('btn-cancel').disabled = true;

            window.pywebview.api.start_install(targetDir, addToPath, embedPy);
        }

        window.onProgress = function(pct, stage, log) {
            document.getElementById('progress-pct').innerText = pct + '%';
            document.getElementById('progress-bar').style.width = pct + '%';
            document.getElementById('progress-stage').innerText = stage;
            if (log) appendLog(log);
        };

        window.onSuccess = function(targetDir) {
            document.getElementById('view-progress').classList.remove('active');
            document.getElementById('view-success').classList.add('active');
            document.getElementById('btn-cancel').style.display = 'none';

            const btnAction = document.getElementById('btn-action');
            btnAction.style.display = 'block';
            btnAction.innerText = 'Abrir Terminal';
            btnAction.onclick = function() {
                window.pywebview.api.launch_terminal(targetDir);
            };

            const footer = document.querySelector('footer');
            const btnExit = document.createElement('button');
            btnExit.className = 'btn btn-secondary';
            btnExit.innerText = 'Salir';
            btnExit.onclick = exitApp;
            footer.insertBefore(btnExit, footer.firstChild);
        };

        window.onError = function(err) {
            appendLog('[ERROR FATAL] ' + err);
            document.getElementById('progress-stage').innerText = 'Fallo en la instalación: ' + err;
            document.getElementById('progress-stage').style.color = '#f85149';
            document.getElementById('btn-cancel').disabled = false;
        };

        function exitApp() {
            window.pywebview.api.exit_app();
        }
    </script>
</body>
</html>
"""

class InstallerApi:
    def __init__(self):
        self.window = None

    def get_system_status(self) -> dict:
        py_ok = is_python_313_or_higher()
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        # Detección de gram
        gram_ok = False
        try:
            import gram
            gram_ok = True
        except ImportError:
            pass

        # Detección de compilador
        compiler_name = ""
        compiler_detail = ""
        gcc = shutil.which('gcc')
        if gcc:
            compiler_name = "GCC"
            compiler_detail = f"Compilador detectado en {gcc}"
        elif shutil.which('cl'):
            compiler_name = "MSVC"
            compiler_detail = "Compilador Microsoft C/C++ detectado"

        return {
            "default_dir": str(get_default_install_dir()),
            "python_ok": py_ok,
            "python_version": f"Python {py_ver}",
            "gram_ok": gram_ok,
            "compiler_name": compiler_name,
            "compiler_detail": compiler_detail,
        }

    def browse_folder(self) -> str | None:
        if not self.window:
            return None
        res = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        return res[0] if res else None

    def start_install(self, target_dir_str: str, add_to_path: bool, force_embed_python: bool):
        target_dir = Path(target_dir_str).resolve()

        def run_thread():
            try:
                def notify(pct, stage, log=""):
                    if self.window:
                        self.window.evaluate_js(f"window.onProgress({pct}, {json.dumps(stage)}, {json.dumps(log)});")

                notify(10, "Creando estructura de carpetas...", f"Destino: {target_dir}")
                repo_root = Path(__file__).resolve().parent.parent

                bin_dir = target_dir / 'bin'
                core_dir = target_dir / 'core'
                lib_dir = target_dir / 'libraries'
                src_dir = target_dir / 'source'
                vendor_dir = target_dir / 'vendor'
                python_dir = target_dir / 'python'

                for d in [bin_dir, core_dir, lib_dir, src_dir, vendor_dir]:
                    d.mkdir(parents=True, exist_ok=True)

                notify(25, "Copiando componentes del compilador...", "Copiando core, libraries y plantillas...")
                for folder_name in ['core', 'libraries', 'source']:
                    src = repo_root / folder_name
                    dst = target_dir / folder_name
                    if src.is_dir():
                        if dst.exists():
                            shutil.rmtree(dst, ignore_errors=True)
                        shutil.copytree(src, dst)

                for single_file in ['egl.py', 'README.md', 'LICENSE']:
                    src = repo_root / single_file
                    if src.is_file():
                        shutil.copy2(src, target_dir / single_file)

                # Python embebido
                need_embed = force_embed_python or not is_python_313_or_higher()
                if need_embed:
                    notify(40, "Configurando entorno de Python 3.13...", "Descargando Python portable oficial...")
                    from tools.installer_core import download_embedded_python
                    download_embedded_python(python_dir)
                    notify(60, "Python 3.13 configurado.", f"Python listo en: {python_dir}")
                else:
                    notify(50, "Python del sistema verificado.", f"Usando Python del sistema.")

                # Gram
                notify(70, "Verificando librería privada 'gram'...", "Configurando vendor/Gram...")
                target_gram = vendor_dir / 'Gram'
                local_gram = repo_root / '.egl' / 'vendor' / 'Gram'
                if local_gram.is_dir() and not target_gram.is_dir():
                    shutil.copytree(local_gram, target_gram)
                elif not (target_gram / 'gram').is_dir():
                    from core.install import install_gram
                    install_gram(target_gram)

                # Compilar / Colocar egl.exe
                notify(85, "Generando lanzador nativo bin/egl.exe...", "Compilando launcher C nativo...")
                from tools.installer_core import compile_launcher_binary
                launcher_c = repo_root / 'tools' / 'launcher.c'
                target_exe = bin_dir / 'egl.exe'
                built_exe = False
                if launcher_c.is_file():
                    built_exe = compile_launcher_binary(launcher_c, target_exe)
                if not built_exe:
                    tools_exe = repo_root / 'tools' / 'egl.exe'
                    if tools_exe.is_file():
                        shutil.copy2(tools_exe, target_exe)

                # egl.cmd
                target_cmd = bin_dir / 'egl.cmd'
                target_cmd.write_text(
                    "@echo off\r\nsetlocal\r\nset \"ROOT=%~dp0..\"\r\n"
                    "if exist \"%ROOT%\\python\\python.exe\" (\r\n"
                    "    \"%ROOT%\\python\\python.exe\" \"%ROOT%\\egl.py\" %*\r\n"
                    ") else (\r\n    python \"%ROOT%\\egl.py\" %*\r\n)\r\n",
                    encoding='utf-8'
                )

                # PATH
                if add_to_path:
                    notify(95, "Registrando en PATH de Windows...", f"Añadiendo {bin_dir} a HKCU\\Environment...")
                    from tools.installer_core import add_to_user_path
                    add_to_user_path(bin_dir)

                notify(100, "¡Instalación completada!", "Easy-C configurado con éxito.")
                if self.window:
                    self.window.evaluate_js(f"window.onSuccess({json.dumps(str(target_dir))});")
            except Exception as e:
                if self.window:
                    self.window.evaluate_js(f"window.onError({json.dumps(str(e))});")

        threading.Thread(target=run_thread, daemon=True).start()

    def launch_terminal(self, target_dir_str: str):
        target_dir = Path(target_dir_str)
        bin_dir = target_dir / 'bin'
        cmd = f'Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd \\"{target_dir}\\"; Write-Host \\"¡Easy-C (EGL) listo para usar! Prueba: egl --version\\""'
        subprocess.Popen(['powershell', '-Command', cmd])
        if self.window:
            self.window.destroy()

    def exit_app(self):
        if self.window:
            self.window.destroy()

def run_gui():
    if not HAS_WEBVIEW:
        print("[Installer Warning] pywebview no está disponible en este entorno. Iniciando modo consola...")
        from tools.installer_core import install_easy_c
        return install_easy_c()

    api = InstallerApi()
    window = webview.create_window(
        title="Instalador Oficial de Easy-C (EGL)",
        html=HTML_CONTENT,
        js_api=api,
        width=780,
        height=620,
        resizable=False,
    )
    api.window = window
    webview.start()
    return 0
