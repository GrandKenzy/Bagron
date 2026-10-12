import sys
import os
import json
import threading
import subprocess
import shutil
import importlib.util
from pathlib import Path

# Protección contra OSError [Errno 22] Invalid argument en modo GUI
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

try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False

from tools.install import get_system_status, install_egl

HTML_CONTENT = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instalador de EGL</title>
    <style>
        :root {
            --bg-body: #f8fafc;
            --bg-card: #ffffff;
            --border: #e2e8f0;
            --border-hover: #cbd5e1;
            --text-main: #0f172a;
            --text-secondary: #475569;
            --text-muted: #94a3b8;
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --success: #16a34a;
            --success-bg: #f0fdf4;
            --success-border: #bbf7d0;
            --info: #0284c7;
            --info-bg: #f0f9ff;
            --info-border: #bae6fd;
            --warning: #d97706;
            --warning-bg: #fffbeb;
            --warning-border: #fef3c7;
            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            user-select: none;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        body {
            background-color: var(--bg-body);
            color: var(--text-main);
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        /* Encabezado */
        header {
            background: #ffffff;
            border-bottom: 1px solid var(--border);
            padding: 16px 28px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .brand-container {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .brand-icon {
            width: 36px;
            height: 36px;
            background: var(--primary);
            color: #ffffff;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 19px;
            font-weight: 800;
            letter-spacing: -0.5px;
        }

        .brand-info h1 {
            font-size: 16px;
            font-weight: 700;
            color: var(--text-main);
        }

        .brand-info p {
            font-size: 12px;
            color: var(--text-muted);
        }

        /* Indicador de pasos / Wizard */
        .wizard-steps {
            display: flex;
            gap: 8px;
            align-items: center;
        }

        .step-item {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            font-weight: 600;
            color: var(--text-muted);
            padding: 4px 10px;
            border-radius: 20px;
            background: #f1f5f9;
            transition: all 0.2s ease;
        }

        .step-item.active {
            background: #eff6ff;
            color: var(--primary);
            border: 1px solid #bfdbfe;
        }

        .step-item.done {
            background: #f0fdf4;
            color: var(--success);
        }

        /* Contenedor principal */
        main {
            flex: 1;
            padding: 24px 32px;
            display: flex;
            flex-direction: column;
            overflow-y: auto;
        }

        .step-view {
            display: none;
            flex-direction: column;
            gap: 20px;
            animation: fadeIn 0.2s ease-out;
        }

        .step-view.active {
            display: flex;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(4px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .title-block h2 {
            font-size: 18px;
            font-weight: 700;
            color: var(--text-main);
            margin-bottom: 4px;
        }

        .title-block p {
            font-size: 13px;
            color: var(--text-secondary);
            line-height: 1.4;
        }

        /* Formulario y Controles */
        .form-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .form-label {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-secondary);
        }

        .input-row {
            display: flex;
            gap: 8px;
        }

        input[type="text"] {
            flex: 1;
            background: #ffffff;
            border: 1px solid var(--border);
            padding: 10px 14px;
            border-radius: 6px;
            font-size: 13px;
            color: var(--text-main);
            outline: none;
            transition: all 0.2s ease;
            box-shadow: var(--shadow-sm);
        }

        input[type="text"]:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
        }

        .checkbox-container {
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 14px 16px;
            display: flex;
            align-items: flex-start;
            gap: 12px;
            box-shadow: var(--shadow-sm);
            cursor: pointer;
            transition: border-color 0.2s;
        }

        .checkbox-container:hover {
            border-color: var(--border-hover);
        }

        .checkbox-container input[type="checkbox"] {
            width: 17px;
            height: 17px;
            margin-top: 2px;
            accent-color: var(--primary);
            cursor: pointer;
        }

        .checkbox-text h4 {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-main);
            margin-bottom: 2px;
        }

        .checkbox-text p {
            font-size: 12px;
            color: var(--text-secondary);
        }

        /* Cards de Diagnóstico */
        .diag-grid {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .diag-card {
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 14px 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: var(--shadow-sm);
        }

        .diag-left {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .diag-icon {
            width: 32px;
            height: 32px;
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 15px;
            font-weight: 700;
            background: #f1f5f9;
            color: var(--text-secondary);
        }

        .diag-text h4 {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-main);
        }

        .diag-text p {
            font-size: 12px;
            color: var(--text-secondary);
        }

        .badge {
            font-size: 11px;
            font-weight: 600;
            padding: 3px 10px;
            border-radius: 20px;
            letter-spacing: 0.2px;
        }

        .badge-success {
            background: var(--success-bg);
            color: var(--success);
            border: 1px solid var(--success-border);
        }

        .badge-info {
            background: var(--info-bg);
            color: var(--info);
            border: 1px solid var(--info-border);
        }

        .badge-warning {
            background: var(--warning-bg);
            color: var(--warning);
            border: 1px solid var(--warning-border);
        }

        /* Barra de Progreso */
        .progress-block {
            display: flex;
            flex-direction: column;
            gap: 12px;
            padding: 10px 0;
        }

        .progress-header {
            display: flex;
            justify-content: space-between;
            font-size: 13px;
            font-weight: 600;
            color: var(--text-secondary);
        }

        .progress-track {
            background: #e2e8f0;
            height: 8px;
            border-radius: 4px;
            overflow: hidden;
        }

        .progress-thumb {
            background: var(--primary);
            height: 100%;
            width: 0%;
            transition: width 0.3s ease;
        }

        .log-box {
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 12px;
            font-family: "Consolas", "Courier New", monospace;
            font-size: 11px;
            color: var(--text-secondary);
            height: 140px;
            overflow-y: auto;
            white-space: pre-wrap;
            box-shadow: inset 0 1px 2px rgba(0,0,0,0.03);
        }

        /* Éxito */
        .success-wrapper {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 24px 0;
            text-align: center;
            gap: 12px;
        }

        .success-badge-large {
            width: 52px;
            height: 52px;
            border-radius: 50%;
            background: var(--success-bg);
            border: 2px solid var(--success-border);
            color: var(--success);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            font-weight: 700;
        }

        .code-box {
            background: #f1f5f9;
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 10px 16px;
            font-family: monospace;
            font-size: 13px;
            color: var(--primary);
            text-align: left;
            margin-top: 8px;
        }

        /* Botones y Footer */
        footer {
            background: #ffffff;
            border-top: 1px solid var(--border);
            padding: 16px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .btn {
            padding: 9px 18px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
            border: none;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }

        .btn-primary {
            background: var(--primary);
            color: #ffffff;
            box-shadow: var(--shadow-sm);
        }

        .btn-primary:hover {
            background: var(--primary-hover);
        }

        .btn-secondary {
            background: #ffffff;
            border: 1px solid var(--border);
            color: var(--text-secondary);
        }

        .btn-secondary:hover {
            background: #f1f5f9;
            border-color: var(--border-hover);
        }

        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
    </style>
</head>
<body>
    <header>
        <div class="brand-container">
            <div class="brand-icon">E</div>
            <div class="brand-info">
                <h1>EGL</h1>
                <p>Instalador Oficial de Sistema</p>
            </div>
        </div>

        <div class="wizard-steps">
            <div class="step-item active" id="step-pill-1">1 Ubicación</div>
            <div class="step-item" id="step-pill-2">2 Diagnóstico</div>
            <div class="step-item" id="step-pill-3">3 Instalación</div>
        </div>
    </header>

    <main>
        <!-- ETAPA 1: RUTA Y PATH -->
        <div class="step-view active" id="view-step-1">
            <div class="title-block">
                <h2>Elige la ruta de instalación</h2>
                <p>Selecciona la carpeta donde se organizarán los componentes del compilador.</p>
            </div>

            <div class="form-group">
                <label class="form-label">Directorio de instalación</label>
                <div class="input-row">
                    <input type="text" id="input-path" spellcheck="false" />
                    <button class="btn btn-secondary" onclick="browseFolder()">Examinar...</button>
                </div>
            </div>

            <label class="checkbox-container">
                <input type="checkbox" id="check-path" checked />
                <div class="checkbox-text">
                    <h4>Agregar EGL al PATH de Windows (Recomendado)</h4>
                    <p>Permite ejecutar el comando <code>egl</code> desde cualquier consola (PowerShell, CMD, Git Bash).</p>
                </div>
            </label>

            <label class="checkbox-container">
                <input type="checkbox" id="check-embed" />
                <div class="checkbox-text">
                    <h4>Descargar entorno Python 3.13 portable de respaldo</h4>
                    <p>Mantiene una copia aislada de Python dentro de la carpeta de EGL para total independencia.</p>
                </div>
            </label>
        </div>

        <!-- ETAPA 2: COMPROBACIONES DEL SISTEMA -->
        <div class="step-view" id="view-step-2">
            <div class="title-block">
                <h2>Comprobación rápida del entorno</h2>
                <p>Verificando dependencias necesarias para asegurar el funcionamiento óptimo:</p>
            </div>

            <div class="diag-grid">
                <!-- Python Card -->
                <div class="diag-card">
                    <div class="diag-left">
                        <div class="diag-icon">Py</div>
                        <div class="diag-text">
                            <h4>Python 3.13+</h4>
                            <p id="diag-desc-python">Comprobando...</p>
                        </div>
                    </div>
                    <span class="badge" id="diag-badge-python">...</span>
                </div>

                <!-- Gram Card -->
                <div class="diag-card">
                    <div class="diag-left">
                        <div class="diag-icon">Gr</div>
                        <div class="diag-text">
                            <h4>Librería Gram</h4>
                            <p id="diag-desc-gram">Comprobando...</p>
                        </div>
                    </div>
                    <span class="badge" id="diag-badge-gram">...</span>
                </div>


            </div>
        </div>

        <!-- ETAPA 3: INSTALACIÓN Y CARGA -->
        <div class="step-view" id="view-step-3">
            <div class="title-block" id="install-header">
                <h2>Instalando EGL...</h2>
                <p>Configurando archivos, módulos del backend y variables de entorno.</p>
            </div>

            <div class="progress-block" id="progress-block">
                <div class="progress-header">
                    <span id="progress-status-text">Iniciando...</span>
                    <span id="progress-percent-text">0%</span>
                </div>
                <div class="progress-track">
                    <div class="progress-thumb" id="progress-bar"></div>
                </div>
            </div>

            <div class="log-box" id="log-output"></div>

            <!-- Éxito Final -->
            <div class="success-wrapper" id="success-wrapper" style="display: none;">
                <div class="success-badge-large">✓</div>
                <h2>¡EGL se ha instalado con éxito!</h2>
                <p style="font-size: 13px; color: var(--text-secondary); max-width: 440px;">
                    El compilador ya está listo. Abre una nueva consola para comenzar a compilar proyectos:
                </p>
                <div class="code-box">
                    egl --version<br>
                    egl run main.egl
                </div>
            </div>
        </div>
    </main>

    <footer>
        <button class="btn btn-secondary" id="btn-back" onclick="goBack()" style="visibility: hidden;">← Atrás</button>
        <div style="display: flex; gap: 8px;">
            <button class="btn btn-secondary" id="btn-cancel" onclick="exitApp()">Cancelar</button>
            <button class="btn btn-primary" id="btn-next" onclick="goNext()">Siguiente →</button>
        </div>
    </footer>

    <script>
        let currentStep = 1;
        let systemData = null;

        window.addEventListener('pywebviewready', function() {
            window.pywebview.api.get_system_status().then(function(data) {
                systemData = data;
                document.getElementById('input-path').value = data.default_dir;

                // Actualizar badges de la etapa 2
                // 1. Python
                const bPy = document.getElementById('diag-badge-python');
                const dPy = document.getElementById('diag-desc-python');
                if (data.python_ok) {
                    bPy.className = 'badge badge-success';
                    bPy.innerText = 'Detectado';
                    dPy.innerText = data.python_msg;
                } else {
                    bPy.className = 'badge badge-info';
                    bPy.innerText = 'Auto-Instalar';
                    dPy.innerText = 'Se descargará Python 3.13 portable automáticamente.';
                    document.getElementById('check-embed').checked = true;
                }

                // 2. Gram
                const bGr = document.getElementById('diag-badge-gram');
                const dGr = document.getElementById('diag-desc-gram');
                if (data.gram_ok) {
                    bGr.className = 'badge badge-success';
                    bGr.innerText = 'Disponible';
                    dGr.innerText = data.gram_msg;
                } else {
                    bGr.className = 'badge badge-info';
                    bGr.innerText = 'Descarga Privada';
                    dGr.innerText = 'Se configurará de forma aislada en vendor/Gram.';
                }


            });
        });

        function updateStepUI() {
            // Actualizar vistas
            document.querySelectorAll('.step-view').forEach(v => v.classList.remove('active'));
            document.getElementById('view-step-' + currentStep).classList.add('active');

            // Actualizar pills
            for (let i = 1; i <= 3; i++) {
                const pill = document.getElementById('step-pill-' + i);
                pill.classList.remove('active', 'done');
                if (i === currentStep) {
                    pill.classList.add('active');
                } else if (i < currentStep) {
                    pill.classList.add('done');
                }
            }

            // Actualizar botones
            const btnBack = document.getElementById('btn-back');
            const btnNext = document.getElementById('btn-next');
            const btnCancel = document.getElementById('btn-cancel');

            if (currentStep === 1) {
                btnBack.style.visibility = 'hidden';
                btnNext.innerText = 'Siguiente →';
                btnNext.style.display = 'inline-flex';
                btnCancel.style.display = 'inline-flex';
            } else if (currentStep === 2) {
                btnBack.style.visibility = 'visible';
                btnNext.innerText = 'Iniciar Instalación →';
                btnNext.style.display = 'inline-flex';
                btnCancel.style.display = 'inline-flex';
            } else if (currentStep === 3) {
                btnBack.style.visibility = 'hidden';
                btnCancel.style.display = 'none';
                btnNext.style.display = 'none';
            }
        }

        function goNext() {
            if (currentStep === 1) {
                currentStep = 2;
                updateStepUI();
            } else if (currentStep === 2) {
                currentStep = 3;
                updateStepUI();
                startInstallationProcess();
            }
        }

        function goBack() {
            if (currentStep === 2) {
                currentStep = 1;
                updateStepUI();
            }
        }

        function browseFolder() {
            window.pywebview.api.browse_folder().then(function(folder) {
                if (folder) {
                    document.getElementById('input-path').value = folder;
                }
            });
        }

        function appendLog(msg) {
            const el = document.getElementById('log-output');
            el.innerText += msg + '\\n';
            el.scrollTop = el.scrollHeight;
        }

        function startInstallationProcess() {
            const targetDir = document.getElementById('input-path').value;
            const addPath = document.getElementById('check-path').checked;
            const embedPy = document.getElementById('check-embed').checked;

            window.pywebview.api.start_install(targetDir, addPath, embedPy);
        }

        window.onProgress = function(pct, statusText, logLine) {
            document.getElementById('progress-bar').style.width = pct + '%';
            document.getElementById('progress-percent-text').innerText = pct + '%';
            document.getElementById('progress-status-text').innerText = statusText;
            if (logLine) appendLog(logLine);
        };

        window.onSuccess = function(targetDir) {
            document.getElementById('install-header').style.display = 'none';
            document.getElementById('progress-block').style.display = 'none';
            document.getElementById('log-output').style.display = 'none';
            document.getElementById('success-wrapper').style.display = 'flex';

            const footer = document.querySelector('footer');
            footer.innerHTML = `
                <div></div>
                <div style="display: flex; gap: 8px;">
                    <button class="btn btn-secondary" onclick="exitApp()">Finalizar</button>
                    <button class="btn btn-primary" onclick="window.pywebview.api.launch_terminal('${targetDir.replace(/\\\\/g, '\\\\\\\\')}')">Abrir Terminal</button>
                </div>
            `;
        };

        window.onError = function(err) {
            document.getElementById('progress-status-text').innerText = 'Error: ' + err;
            document.getElementById('progress-status-text').style.color = '#dc2626';
            appendLog('[ERROR FATAL] ' + err);

            const footer = document.querySelector('footer');
            footer.innerHTML = `
                <div></div>
                <button class="btn btn-secondary" onclick="exitApp()">Cerrar</button>
            `;
        };

        function exitApp() {
            window.pywebview.api.exit_app();
        }
    </script>
</body>
</html>
"""

class FastInstallerApi:
    def __init__(self):
        self.window = None

    def get_system_status(self) -> dict:
        return get_system_status()

    def browse_folder(self) -> str | None:
        if not self.window:
            return None
        res = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        return res[0] if res else None

    def start_install(self, target_dir_str: str, add_to_path: bool, force_embed_python: bool):
        target_dir = Path(target_dir_str).resolve()

        def worker():
            try:
                def notify(pct, stage, log=""):
                    if self.window:
                        self.window.evaluate_js(f"window.onProgress({pct}, {json.dumps(stage)}, {json.dumps(log)});")

                install_egl(
                    target_dir=target_dir,
                    force_embed_python=force_embed_python,
                    add_to_path=add_to_path,
                    progress=notify,
                )
                if self.window:
                    self.window.evaluate_js(f"window.onSuccess({json.dumps(str(target_dir))});")
            except Exception as e:
                if self.window:
                    self.window.evaluate_js(f"window.onError({json.dumps(str(e))});")

        threading.Thread(target=worker, daemon=True).start()

    def launch_terminal(self, target_dir_str: str):
        target_dir = Path(target_dir_str)
        cmd = f'Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd \\"{target_dir}\\"; Write-Host \\"¡EGL listo! Prueba: egl --version\\""'
        subprocess.Popen(['powershell', '-Command', cmd])
        if self.window:
            self.window.destroy()

    def exit_app(self):
        if self.window:
            self.window.destroy()

def run_gui():
    if not HAS_WEBVIEW:
        print("[Installer Warning] pywebview no está disponible. Ejecutando en modo consola...")
        from tools.install import install_egl
        return install_egl()

    api = FastInstallerApi()
    window = webview.create_window(
        title="Instalador Oficial de EGL",
        html=HTML_CONTENT,
        js_api=api,
        width=740,
        height=560,
        resizable=False,
    )
    api.window = window
    webview.start()
    return 0
