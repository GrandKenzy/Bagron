# Guía de Instalación, Actualización y Desinstalación

Esta guía detalla los métodos oficiales para instalar, configurar, actualizar y desinstalar el compilador **EGL** en tu sistema.

---

## 📋 Requisitos del Sistema

* **Sistema Operativo:** Windows 10/11 (64-bit), Linux o macOS.
* **Python:** Python 3.13 o superior instalado y disponible en el PATH (requerido por el frontend y soporte avanzado de f-strings PEP 701).
* **Compilador C (Opcional para compilación estática a C; requerido para compilar a binario):**
  * GCC (MinGW-w64 en Windows o gcc nativo en Linux).
  * Clang.
  * MSVC (Visual Studio / Build Tools).
  * TinyCC (TCC).

> [!NOTE]
> EGL genera código C estándar (`C99/C11`). Puedes usar EGL para generar únicamente el archivo monolítico `program.c` sin necesidad de un compilador C instalado. Solo necesitas GCC/Clang/MSVC si utilizas las banderas `--build` o `--run`.

---

## 🚀 Método 1: Instalador Oficial para Windows (`egl-installer.exe`)

Es la forma más rápida y recomendada para usuarios finales en Windows.

### 1. Descarga
Descarga el ejecutable `egl-installer.exe` desde la última versión en [Releases de GitHub](https://github.com/GrandKenzy/EGL/releases).

### 2. Instalación con Interfaz Gráfica (GUI)
Haz doble clic sobre `egl-installer.exe`. Se abrirá una interfaz moderna que te permitirá:
* Seleccionar la carpeta de instalación (por defecto: `%LOCALAPPDATA%\Programs\EGL`).
* Decidir si deseas añadir EGL al PATH del usuario.
* Instalar automáticamente con un solo clic.

### 3. Instalación desde Consola (Modo CLI)
Si prefieres instalar desde la terminal (PowerShell o CMD) o en entornos automatizados:

```cmd
:: Instalación estándar interactiva en consola
egl-installer.exe --cli

:: Instalación en una ruta personalizada
egl-installer.exe --cli --target "C:\Herramientas\EGL"

:: Instalar sin modificar las variables de entorno PATH
egl-installer.exe --cli --no-path
```

---

## 🛠️ Método 2: Instalación desde el Código Fuente (Desarrolladores)

Ideal si deseas contribuir al desarrollo del compilador o trabajar con la versión más reciente del repositorio:

### 1. Clonar el repositorio
```bash
git clone https://github.com/GrandKenzy/EGL.git
cd EGL
```

### 2. Instalar el motor sintáctico Gram
EGL requiere la librería privada `gram` para su frontend léxico y sintáctico. Puedes instalarla de forma aislada en `.egl/vendor/Gram`:
```bash
python egl.py install gram
```

### 3. (Opcional) Instalar EGL en el sistema mediante el script instalador
Puedes correr el instalador en modo CLI para copiar los binarios a `%LOCALAPPDATA%\Programs\EGL` y agregarlo al PATH:
```bash
python installer.py --cli
```

---

## 📁 Estructura del Directorio Instalado

Cuando EGL se instala en tu sistema (por ejemplo en `%LOCALAPPDATA%\Programs\EGL`), los archivos quedan organizados de la siguiente forma limpia y desacoplada:

```text
%LOCALAPPDATA%\Programs\EGL\
├── bin\
│   ├── egl.exe             # Envoltorio ejecutable para invocar el compilador
│   ├── egl.cmd             # Lanzador batch alternativo
│   ├── egl-uninstall.cmd   # Lanzador directo de desinstalación
│   └── uninstaller.py      # Script autónomo desacoplado de desinstalación
├── core\                   # Núcleo del compilador (AST, procesador, backend C)
├── EGLLibs\                # Librerías estándar de EGL (módulos y bindings)
├── vendor\
│   └── Gram\               # Motor sintáctico Gram (sin metadatos git)
├── egl.py                  # Punto de entrada de la suite
└── README.md               # Documentación y referencia
```

---

## 🔄 Cómo Actualizar EGL

EGL cuenta con un comando integrado para actualizarse a la versión más reciente publicada en el repositorio oficial:

```bash
# Comprobar y actualizar automáticamente:
egl update

# Forzar la reinstalación/actualización completa:
egl update --force
```

El actualizador descargará los archivos más recientes, actualizará las dependencias y preservará tus configuraciones.

---

## 🗑️ Cómo Desinstalar EGL

Tienes tres opciones para remover EGL completamente de tu sistema:

### Opción A: Desde la Configuración de Windows (Recomendado)
1. Abre **Configuración de Windows** (Win + I) -> **Aplicaciones** -> **Aplicaciones instaladas** (o *Agregar o quitar programas*).
2. Busca **EGL Compiler**.
3. Haz clic en **Desinstalar**. El desinstalador autónomo se ejecutará en segundo plano, limpiará el registro de Windows, removerá la ruta de la variable `PATH` del usuario y borrará todos los archivos instalados.

### Opción B: Desde cualquier terminal (Comando directo)
Si tienes EGL en tu PATH, simplemente ejecuta:
```cmd
egl-uninstall
```
Este comando invoca el lanzador autónomo en `bin\egl-uninstall.cmd`, el cual se desacopla del proceso activo, espera que la consola libere los archivos y elimina la instalación sin errores de bloqueo (`WinError 32` / `WinError 5`).

### Opción C: Usando el instalador original
Si conservas `egl-installer.exe` o el repositorio:
```cmd
egl-installer.exe --uninstall
# o desde el código fuente:
python installer.py --uninstall
```

---

## ❓ Solución de Problemas Comunes

### 1. `egl` no se reconoce como un comando interno o externo
* Asegúrate de cerrar y volver a abrir tu terminal (PowerShell/CMD) después de la instalación para que Windows recargue las variables de entorno.
* Verifica manualmente que `%LOCALAPPDATA%\Programs\EGL\bin` esté presente en tu variable de entorno `PATH` de usuario.

### 2. Error al compilar con `--build` o `--run`: `gcc no se reconoce...`
* EGL generó tu archivo `program.c` con éxito, pero tu sistema no tiene un compilador C en el PATH.
* Instala MinGW-w64 (GCC), Clang o ejecuta `egl download gcc` para configurar uno automáticamente.
