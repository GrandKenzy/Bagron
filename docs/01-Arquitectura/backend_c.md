# Backend C y Ensamblador Monolitico

El backend C (`core/backend/c`) es el motor de generacion de codigo de Easy-C. Su mision es traducir la coleccion de objetos semanticos intermedios generados por el procesador a un archivo fuente monolítico en lenguaje C conforme a los estandares C99/C11, garantizando que el archivo resultante sea autonomo, estricto en tipos y compilar directamente con GCC o Clang sin advertencias.

---

## Especificacion Tecnica

El proceso de emision se compone de tres etapas: analisis de dependencias y deteccion de cabeceras, emision individualizada de objetos mediante visitantes, y ensamblado estructural en `core/compiler.py`.

### 1. Deteccion Automatica de Cabeceras (`detectors.py`)

A diferencia de los compiladores tradicionales que exigen declaraciones manuales de `#include` para tipos estandar, Easy-C analiza estaticamente las variables, parametros y llamadas para inferir las librerias minimas necesarias del sistema:

* `<stdint.h>`: Se incluye si se utiliza cualquier tipo entero de tamaño fijo (`int8_t`, `int16_t`, `int32_t`, `int64_t`, `uint8_t`, etc.).
* `<stdbool.h>`: Se incluye si se utilizan tipos o literales booleanos (`bool`, `true`, `false`).
* `<stdio.h>`: Se incluye si se invocan simbolos del sistema de entrada/salida (`print`, `printf`, `puts`, `scanf`, etc.).
* `<stdlib.h>`: Se incluye ante llamadas de gestion de memoria dinamica o utilidades del sistema (`malloc`, `free`, `calloc`, `realloc`, `exit`, `abs`, etc.).

Las cabeceras detectadas se registran globalmente en `c.includes` mediante `add_include()`, evitando duplicaciones.

---

## Visitantes del Backend C (`core/backend/c/visitors/`)

Cada objeto semantico es procesado por un modulo visitante especializado:

### `variable.py`
Transforma instancias de `Variable` en definiciones C:
* Las constantes (`NOMBRE_MAYUSCULA`) o variables privadas se califican con `static` o `const` segun su visibilidad.
* Resuelve inicializaciones complejas: literales de cadena (`char*` o `char[]`), arrays de longitud fija (`T name[N]`), punteros (`void* name = NULL`) o asignaciones derivadas de llamadas a funciones (`T name = func();`).

### `function.py`
Genera la cabecera y el cuerpo de funciones C:
* Valida la concordancia entre el tipo de retorno declarado (`return_type`) y el valor efectivo retornado en `Returned`.
* Si el retorno es un identificador o parametro (`FunctionParam`), extrae su tipo mediante indexacion de tupla o propiedad `type`.
* Si el retorno es una expresion aritmetica/logica (ej. `return valor * 2`), la procesa mediante `format_expression` sin forzar comprobaciones de literales individuales.
* Genera modificadores de visibilidad (`static` si la funcion es privada).

### `expression.py`
Normaliza y reescribe expresiones EGL para C:
* **Metapropiedades Magicas:**
  * `v.type` -> Cadena literal con el nombre del tipo (ej. `"int"` o `"array[int, 10]"`).
  * `v.ptr` -> Direccion de memoria de la variable (`&v`).
  * `v.size` -> Expresion de tamaño (`sizeof(tipo)` o `sizeof(elem) * N`).
  * `v.len` -> Longitud estatica del buffer o array.
  * `v.__const__` / `v.const` -> `"1"` si la variable es inmutable; `"0"` en caso contrario.
  * `v.__visibility__` / `v.visibility` -> `"0"` si es privada; `"1"` si es publica.
  * `v.value` -> Lanza una excepcion en tiempo de compilacion, protegiendo el acceso a la representacion interna del tipo.
* **Control de Identificadores:** Unicamente resuelve nombres de variables individuales mediante expresiones regulares estrictas (`^[A-Za-z_][A-Za-z0-9_]*$`), evitando que operadores aritmeticos sean confundidos con identificadores existentes.

### `deffunc.py`
Controla la emision de llamadas a funciones (`Call`):
* `print(...)`: Formatea automaticamente los especificadores de conversion (`%lld`, `%s`, `%d`, `%f`, `%p`) e inyecta la llamada `printf("...", args);` con salto de linea implicito.
* `free(ptr)`: Inyecta llamada nativa de liberacion de memoria y asegura inclusion de `<stdlib.h>`.
* `__size__(T)`: Emite `sizeof(T)` directamente a nivel de compilador.
* Funciones `inline`: Expande inline las funciones registradas mediante `core/backend/c/inline.py`.

---

## Ensamblado Monolitico (`core/compiler.py`)

La funcion `compile_project()` une todos los componentes en un unico archivo de salida (`program.c`):

1. **Cabeceras C:** Consolida directivas `#include` (provenientes de `include` explicitos y de detectores estaticos) y las deduplica preservando el orden.
2. **Definiciones de Tipos:** Emite los `typedef` y estructuras globales.
3. **Prototipos Adelantados (*Forward Declarations*):** Genera la firma con punto y coma de cada funcion de modulo (ej. `int64_t inmodule_modulo_funcion(int64_t arg);`) para permitir llamadas recursivas o intermodulares sin advertencias de declaracion implicita.
4. **Implementaciones de Funciones:** Escribe el cuerpo completo de las funciones de modulo y funciones globales.
5. **Punto de Entrada `main` Sintetico:**
   * Si el usuario no definio una funcion `main` explicita, el compilador genera:
   ```c
   int main(int argc, char** argv) {
       // Sentencias ejecutables de nivel raiz
       return 0;
   }
   ```
   * Esto permite que scripts directos de Easy-C con declaraciones e invocaciones a nivel de raiz operen como programas validos en C.
