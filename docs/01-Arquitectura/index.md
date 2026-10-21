# Arquitectura Del Compilador Easy-C (c-)

Este documento detalla la arquitectura tecnica del compilador **Easy-C** (nombrado tambien como **c-**), sus principios de diseno, la integracion del frontend con **Gram** y **VNMA**, el procesador semantico y el backend generador de codigo C monolitico.

---

## Principios De Diseno

Easy-C fue concebido como un lenguaje de programacion de tipado estatico y sintaxis limpia basada en indentacion, con un objetivo estricto: **generar codigo C monolitico de alto rendimiento sin intermediarios**.

**anti sobre carga de runtime (no runtime cost):**
c- no implementa recolector de basura (Garbage Collector), ni maquina virtual de bytecode, ni bucle de eventos oculto. Las estructuras definidas en Easy-C mapean directamente a structs estandar de C, y los tipos escalares corresponden a anchos exactos de registros de la CPU.

**compilacion C (codigo monolito):**
En lugar de generar multiples unidades de traduccion compiladas de forma independiente que requieran enlaces complejos durante el prototipado, el compilador emite un unico archivo `build/program.c`. Todo el arbol de dependencias modulos locales y funciones se organizan y resuelven en un solo archivo plano optimizable por el backend del compilador de C nativo (GCC, Clang o MSVC).

**separar fases:**
El pipeline de compilacion desacopla por completo el analisis sintactico del analisis semantico. El motor sintactico **Gram** no valida tipos ni resuelve simbolos; unicamente produce un arbol de sintaxis abstracta (AST). Es el procesador semantico (`core/processor`) quien aplica las reglas de inferencia, control de ambitos y compatibilidad binaria.

---

## Pipeline De Compilacion

El pipeline procesa el codigo fuente a traves de etapas consecutivas y transaccionales:

```
+=================================================================================+
||                        Pipeline De Compilacion De c-                          ||
+=================================================================================+

  +-------------------+
  | LEXER             |  Ingesta de lineas UTF-8, tokenizacion mediante automatas
  | (Gram Lexer)      |  de Gram, emision de tokens IDENT, NUMBER, STRING,
  +-------------------+  simbolos y bloques INDENT/DEDENT para indentacion.
            |
            v
  +-------------------+
  | PARSER            |  Construccion del AST a traves de Combinadores de Gram,
  | (Gram Parser)     |  evaluacion declarativa con retroceso transaccional
  +-------------------+  (savepoint/restore), emision de arboles ASTRef.
            |
            v
  +-------------------+
  | PROCESSOR         |  Inspeccion y tipado en core/processor, resolucion de
  | (Processor)       |  ambitos y tablas de simbolos (Storage), calculo de
  +-------------------+  anchos de tipos (typesys.py) y validacion de llamadas.
            |
            v
  +-------------------+
  | BACKEND           |  Linearizacion topologica de modulos (ordered_modules),
  | (Backend EC)      |  mangling determinista de identificadores y emision del
  +-------------------+  archivo final monolitico C99/C11 (program.c).

```

---

## Frontend Gramatical Y Gestion Con VNMA

### Integracion De Gram Mediante VNMA
Easy-C aisla sus dependencias mediante el gestor de entornos **VNMA**, evitando la instalacion de paquetes globales en el sistema operativo:

- **Archivo `vnma.toml`:**
  Declara `gram-framework` como dependencia local editable para desarrollo continuo:
  ```toml
  [project]
  name = "easyc"
  version = "1.0.0"

  [dependencies]
  gram-framework = { path = "~/Desktop/Gram", editable = true }

  [tool.vnma]
  vendor_dir = "vendor"
  ide_integration = ["vscode", "pycharm"]
  ```

- **Bloqueo reproducible (`vnma.lock`):**
  Congela la version exacta de Python y la fuente del framework sintactico para reproducibilidad binaria estricta.

- **Ejecucion (`vnma run`):**
  Las herramientas y pruebas se lanzan dentro del entorno gestionado (`vnma run`), resolviendo las importaciones de Gram sin inyectar rutas artificiales en `PYTHONPATH`.

- **Directorio `vendor/`:**
  Permite empaquetar o congelar las dependencias de Gram para compilacion local aislada sin requerir red.

### Configuracion Del Motor Lexico
Antes de instanciar el analizador sintactico, c- inicializa las opciones globales de Gram en [`core/initiator/keywords.py`](../../core/initiator/keywords.py):

```python
from gram import config, lexer

config.LEXER_COMMENT_TOKEN = ';'            # Comentarios mono-linea
config.LEXER_SAVE_COMMENTS = False          # Descarta comentarios del stream
config.INFO_GENERATE_LOGFILE = True         # Telemetria y trazado de ejecucion
config.PARSER_ADD_INFO = True               # Metadatos de depuracion en AST
config.INFO_GENERATE_LOGFILE_ON_ERROR = True# Volcado al ocurrir fallo lexico

lexer.words.clear_all()
```

### Categorias De Combinadores Sintacticos
c- estructura su gramatica mediante los combinadores de Gram definidos en `gram/core/combinators/`:

- **Matching:** `MatchToken` para validar tokens no reservados (identificadores, literales, indentaciones); `MatchKeyword` para sentencias fijas (`return`, `while`, `struct`); y `MatchGroup` para familias de palabras registradas (`types`, `privacy`, `clauses`, `iters`).
- **Estructurales:** `Seq` para secuencias transaccionales con `savepoint`/`restore`; `Alt` para evaluar ramificaciones sintacticas; `Opt` para clausulas opcionales; y `Enclosed` para delimitar parentesis y llaves.
- **Repeticion:** `Many` (cero o mas repeticiones); `Some` (una o mas); y `Separator` para secuencias delimitadas por coma o punto con soporte de separadores terminales.
- **Reglas y Almacenamiento:** `RuleItem` como clase base con control de envoltura en nodo (`nodeable = True/False`) y `Ref` para resolucion diferida en gramaticas recursivas.
- **Expresiones Pratt (`DualExpr`):** Delega la precedencia de operadores aditivos, multiplicativos, relacionales y bit a bit al motor de Pratt parsing de Gram.

---

## Procesador Semantico (`core/processor`)

El despachador semantico toma el arbol `ASTRef` generado por Gram y produce entidades tipadas registradas en la tabla de simbolos:

```
  [ Arbol AST de Gram (ast.ASTRef) ]
                 |
                 v
  +-------------------------------+
  | processor.process() Dispatcher|  Despacha cada nodo raiz a su visitante semantico
  +-------------------------------+
                 |
    +------------+------------+------------+
    |                         |            |
    v                         v            v
  [ var_decl ]              [ func_decl ] [ struct_decl / class_decl ]
    |                         |            |
    v                         v            v
  Valida tipos              Crea ambito    Resuelve empaque (__packed__),
  con typesys.py            LocalStorage   alineacion (__align__) y metodos
    |                         |            |
    +------------+------------+------------+
                 |
                 v
  +-------------------------------+
  |     Tabla Storage Global      |  variables, functions, structs, classes,
  |  - bpoint (orden cronologico) |  includes, externs y modulos ordenados.
  +-------------------------------+
```

### Tabla De Simbolos (`Storage`)
Ubicada en [`core/processor/storage.py`](../../core/processor/storage.py), almacena el contexto completo del archivo fuente o modulo:

- Contenedores de simbolos: diccionarios para `variables`, `functions`, `structs`, `enums`, `classes`, `types` e `imports`.
- Puntero de emision lineal (`bpoint`): registra el orden cronologico de declaraciones para que el backend de C respete las dependencias naturales del codigo.
- Deteccion de colisiones (`collition_name`): previene sobreescrituras contra funciones magicas del sistema y definiciones duplicadas.

### Sistema De Tipos (`typesys.py`)
Mapea primitivas de maquina contra tipos escalares C (enteros con y sin signo de 8, 16, 32 y 64 bits, flotantes IEEE-754 y punteros). Valida estrictamente la seguridad de punteros prohibiendo la conversion de `cptr` (solo lectura) a `ptr` (mutable).

---

## Backend Monolitico C (`core/backend/ec`)

Traduce las estructuras de la tabla de simbolos a un unico archivo de salida `build/program.c`:

- **Contenedor `Files`:** Administra la generacion del codigo de cabeceras, declaraciones adelantadas y cuerpos de funciones en `program.c` (y opcionalmente `program.h` si se solicita exportar prototipos).
- **Emision topologica:** Itera sobre `storage.ordered_modules` para emitir dependencias en orden inverso de profundidad antes de compilar el archivo principal.
- **Name Mangling:** Aplica prefijos deterministas (`<modulo>_<simbolo>`) a las entidades privadas de los submodulos, protegiendo el espacio de nombres global de C.
- **Optimizacion nativa:** El archivo monolitico resultante es compilado directamente con GCC, Clang o MSVC con el maximo nivel de optimizacion en linea (`-O2` / `-O3`).
