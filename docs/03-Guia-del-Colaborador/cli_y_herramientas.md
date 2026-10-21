# Interfaz De Linea De Comandos (CLI) Y Herramientas

Este documento detalla la interfaz de linea de comandos, las herramientas auxiliares, el lanzador nativo de Windows y la integracion de desarrollo para **Easy-C** (o **c-**).

---

## Sintaxis General Del CLI

El CLI permite compilar, ejecutar, gestionar dependencias y desplegar extensiones:

```bash
egl compile [ruta] [-o <salida.c>] [--build] [--run] [--cc <compilador>] [-l <lib>] [-I <dir>] [-L <dir>]
egl run [ruta] [-o <salida.c>] [--cc <compilador>] [-l <lib>] [-I <dir>] [-L <dir>]
egl cache clear
egl extension [--install] [-o <ruta.vsix>]
egl --version
egl --help
```

---

## Catalogo De Comandos Y Opciones

| Opcion / Argumento | Tipo | Valor Por Defecto | Descripcion |
| :--- | :--- | :--- | :--- |
| `compile [ruta]` | Comando | `'source'` o `'.'` | Transpila el codigo fuente Easy-C a codigo C monolitico (`program.c`). |
| `run [ruta]` | Comando | `'source'` o `'.'` | Compila a C, construye el binario nativo y lo ejecuta de inmediato. |
| `cache clear` | Comando | N/A | Elimina directorios temporales y cache de compilacion (`.cache`, `__pycache__`, `.pyc`). |
| `extension` | Comando | N/A | Genera la extension oficial para Visual Studio Code (`.vsix`) con tema Noble Dark y gramatica TextMate. |
| `-b`, `--build` | Flag | `False` | Tras generar `program.c`, invoca el compilador C nativo para generar el binario (`.exe` o ejecutable ELF). |
| `-r`, `--run` | Flag | `False` | Construye el ejecutable y lo lanza inmediatamente. |
| `-o`, `--output` | Opcion | `program.c` | Ruta o nombre del archivo C monolitico de salida. |
| `--cc` | Opcion | `gcc` | Compilador nativo a invocar (`gcc`, `clang`, `cl` / `msvc`, `tcc`). |
| `-l`, `--link` | Opcion | N/A | Bandera de enlace para librerias externas (ej. `-l SDL3`). Admite multiples ocurrencias. |
| `-I`, `--include` | Opcion | N/A | Agrega un directorio de cabeceras C (`-I <dir>`). |
| `-L`, `--lib-dir` | Opcion | N/A | Agrega un directorio de librerias binarias para el linker (`-L <dir>`). |
| `--install` | Flag | `False` | Utilizado con `extension`: instala automaticamente el `.vsix` en VS Code mediante `code --install-extension`. |
| `-v`, `--version` | Flag | N/A | Informa la version actual del compilador. |
| `-h`, `--help` | Flag | N/A | Imprime la guia rapida de opciones en terminal. |

---

## Lanzador Nativo Win32 (`tools/launcher.c`)

Para evitar la latencia de arranque de interpretes de scripting o archivos `.bat`, c- implementa un lanzador nativo compilado en C (`egl.exe`):

- Detecta la ruta absoluta del binario mediante `GetModuleFileNameW`.
- Localiza el interprete de Python embebido o del entorno virtual.
- Configura variables de entorno criticas y despacha la ejecucion con `CreateProcessW` con latencia cercana a cero.

---

## Ejecucion Con El Gestor VNMA

Para tareas de desarrollo sobre el compilador, las dependencias con **Gram** se ejecutan en el entorno aislado provisto por **VNMA**:

```bash
# Ejecutar el orquestador de compilacion dentro del entorno VNMA:
vnma run python main.py compile source --build

# Lanzar tests o diagnosticos sin tocar paquetes globales:
vnma run python -m unittest discover tests/
```

VNMA resuelve el paquete `gram-framework` declarado en `vnma.toml` en modo editable, garantizando que el compilador opere siempre sobre la version correcta del arbol sintactico.

---

## Generacion De Extension Para VS Code (`vsix`)

Easy-C incorpora un generador automatico de sintaxis TextMate que extrae dinamicamente las palabras reservadas registradas en el compilador:

```bash
# Construir el empaquetado vsix en la raiz del proyecto:
egl extension

# Construir e instalar directamente en VS Code:
egl extension --install

# Especificar ruta personalizada:
egl extension -o dist/easyc-syntax.vsix
```

---

## Sistema De Diagnostico (`tools/diagnostic.py`)

Hereda de las utilidades de diagnostico de Gram para registrar telemetria del AST y volcados de errores:

- Crea registros jerarquicos de procesamiento en la carpeta `log/`.
- Permite registrar nodos del arbol sintactico ante excepciones semanticas mediante `generate_on_error = True`.
- Opera de forma limpia al invocarse con `vnma run` sin requerir modificaciones en tiempo de ejecucion.

---

## Uso Programatico Desde Python

El pipeline de compilacion puede ser importado como modulo de Python para suites de integracion o herramientas externas:

```python
from pathlib import Path
from core.compiler import compile_source

origen = Path("source/main.egl")
storage = compile_source(origen)

print(f"Modulos procesados: {len(storage.ordered_modules)}")
```
