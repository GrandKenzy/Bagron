# Interfaz de Linea de Comandos (CLI) y Herramientas

Easy-C (EGL) incluye una interfaz de linea de comandos moderna y minimalista diseñada tanto para flujos de trabajo en consola como para integracion en pipelines de integracion continua (CI/CD). La implementacion se encuentra desacoplada entre el despachador de argumentos (`core/cli.py`), el punto de entrada ejecutable (`egl.py`) y el lanzador rapido para Windows (`egl.bat`).

---

## Especificacion de Comandos

### Sintaxis General

```bash
egl compile [ruta] [-o <salida.c>] [--build] [--run] [--cc <compilador>] [-l <lib>] [-I <dir>] [-L <dir>]
egl run [ruta] [-o <salida.c>] [--cc <compilador>] [-l <lib>] [-I <dir>] [-L <dir>]
egl cache clear
egl extension [--install] [-o <ruta.vsix>]
egl --version
egl --help
```

### Comandos y Opciones

| Opcion / Argumento | Tipo | Valor por Defecto | Descripcion |
| :--- | :--- | :--- | :--- |
| `compile [ruta]` | Comando | `'source'` o `'.'` | Compila el proyecto EGL. Si no se especifica ruta, busca automaticamente en `source` o el directorio actual. |
| `run [ruta]` | Comando | `'source'` o `'.'` | Compila, construye el ejecutable nativo y lo ejecuta directamente (equivalente a `compile [ruta] --run`). |
| `cache clear` | Comando | N/A | Limpia y elimina todos los archivos y carpetas de cache del proyecto (`.cache`, `__pycache__`, `.pyc`). Alias: `clean`. |
| `extension` | Comando | N/A | Genera el paquete oficial de extension para VS Code (`.vsix`) con resaltado de sintaxis TextMate y tema Noble Dark. Aliases: `vsix`, `syntax`. |
| `-b`, `--build` | Flag | `False` | Tras generar el archivo C, invoca el compilador nativo (GCC) para generar el ejecutable (`program.exe` en Windows o `program` en POSIX). |
| `-r`, `--run` | Flag | `False` | Compila con GCC y ejecuta el binario inmediatamente. Puede posicionarse antes o despues de la ruta. |
| `-o`, `--output` | Opcion | `program.c` | Nombre o ruta del archivo de codigo C monolitico generado (o ruta destino del `.vsix` en el comando `extension`). |
| `--cc` | Opcion | `gcc` | Compilador de C a invocar cuando se utiliza `--build` o `--run` (ej. `gcc`, `clang`, `tcc`). |
| `-l`, `--link` | Opcion | N/A | Enlaza una libreria externa adicional al invocar el compilador de C (ej. `-l SDL3`). Admite multiples ocurrencias. |
| `-I`, `--include` | Opcion | N/A | Agrega una carpeta de cabeceras de C (`.h`) a la linea de compilacion de GCC (`-I <dir>`). |
| `-L`, `--lib-dir` | Opcion | N/A | Agrega una carpeta de librerias binarias al linker de GCC (`-L <dir>`). |
| `--install` | Flag | `False` | Utilizado con `extension`: instala de forma automatica el `.vsix` en Visual Studio Code mediante el comando `code --install-extension`. |
| `-v`, `--version` | Flag | N/A | Muestra la version actual del compilador Easy-C. |
| `-h`, `--help` | Flag | N/A | Muestra la guia de uso y catalogo de opciones en consola. |

---

## Modos de Ejecucion

### 1. Ejecucion en Windows mediante Lanzador Batch
El archivo `egl.bat` en la raiz del proyecto actua como puente directo con el interprete de Python activo:

```cmd
egl.bat compile source --build
egl.bat run source
egl.bat extension --install
```

### 2. Ejecucion Multiplataforma (Linux / macOS / Windows)
Directamente a traves del interprete de Python:

```bash
python egl.py compile source --build
python egl.py run source
python egl.py extension --install
```

### 3. Generacion e Instalacion de la Extension para VS Code (`vsix`)
Easy-C incluye un generador dinámico de sintaxis TextMate sincronizado con las palabras clave reales del compilador. Para empaquetar la extension oficial de Visual Studio Code:

```bash
# Generar el archivo .vsix en la raiz del proyecto:
python egl.py extension

# Generar e instalar automaticamente en VS Code:
python egl.py extension --install

# Especificar un archivo de salida personalizado:
python egl.py extension -o dist/easy-c-syntax.vsix
```

### 4. Salida Estandar del Comando `--run`
Al ejecutar con `--run`, el CLI imprime de forma ordenada los hitos del proceso y enmarca la salida directa del binario:

```text
[EGL] Compilando proyecto en: 'source'
[EGL] Archivo monolítico generado exitosamente: 'program.c'
[EGL] Compilando con gcc: 'program.exe'...
[EGL] Ejecutando: 'program.exe'
--- Salida del programa ---
Resultado: 42
---------------------------
```

---

## Uso Programatico desde Python

Para suites de pruebas o herramientas de automatizacion, la funcion `compile_project()` puede invocarse directamente como libreria Python:

```python
from pathlib import Path
from core.compiler import compile_project

ruta_fuente = Path("source")
ruta_salida_c = compile_project(ruta_fuente, output_file="binario.c")

print(f"Archivo generado en: {ruta_salida_c.resolve()}")
```

### Parametros de `compile_project()`:
* `source_path` (`str | Path`): Ruta al directorio que contiene `main.egl` o ruta directa al archivo fuente.
* `output_file` (`str | Path`, opcional): Ruta del archivo C destino (por defecto `'program.c'`).
* `entrypoint_func` (`str | None`, opcional): Nombre de una funcion de entrada alternativa si no se desea usar `main`.
* **Retorno (`Path`):** Instancia de `pathlib.Path` con la ubicacion absoluta del archivo `.c` generado.
