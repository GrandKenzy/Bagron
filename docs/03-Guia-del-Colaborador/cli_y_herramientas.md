# Interfaz de Linea de Comandos (CLI) y Herramientas

Easy-C (EGL) incluye una interfaz de linea de comandos moderna y minimalista diseñada tanto para flujos de trabajo en consola como para integracion en pipelines de integracion continua (CI/CD). La implementacion se encuentra desacoplada entre el despachador de argumentos (`core/cli.py`), el punto de entrada ejecutable (`egl.py`) y el lanzador rapido para Windows (`egl.bat`).

---

## Especificacion de Comandos

### Sintaxis General

```bash
egl compile <ruta> [-o <salida.c>] [--run] [--cc <compilador>]
egl --version
egl --help
```

### Comandos y Opciones

| Opcion / Argumento | Tipo | Valor por Defecto | Descripcion |
| :--- | :--- | :--- | :--- |
| `compile <ruta>` | Comando | Obligatorio | Compila el proyecto ubicado en `<ruta>`. Requiere que el directorio contenga un archivo `main.egl`. |
| `-o`, `--output` | Opcion | `program.c` | Nombre o ruta del archivo de codigo C monolitico generado. |
| `-r`, `--run` | Flag | `False` | Tras generar el archivo C, invoca el compilador nativo (GCC) y ejecuta el binario inmediatamente. |
| `--cc` | Opcion | `gcc` | Compilador de C a invocar cuando se utiliza el flag `--run` (ej. `gcc`, `clang`, `tcc`). |
| `-v`, `--version` | Flag | N/A | Muestra la version actual del compilador Easy-C. |
| `-h`, `--help` | Flag | N/A | Muestra la guia de uso y catalogo de opciones en consola. |

---

## Modos de Ejecucion

### 1. Ejecucion en Windows mediante Lanzador Batch
El archivo `egl.bat` en la raiz del proyecto actua como puente directo con el interprete de Python activo:

```cmd
egl.bat compile source --run
```

### 2. Ejecucion Multiplataforma (Linux / macOS / Windows)
Directamente a traves del interprete de Python:

```bash
python egl.py compile source -o salida.c --run
```

### 3. Salida Estandar del Comando `--run`
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
