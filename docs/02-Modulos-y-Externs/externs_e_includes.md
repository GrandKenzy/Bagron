# Includes y Definiciones Externas (Externs)

Easy-C (EGL) permite interoperabilidad directa con librerias nativas de C mediante la directiva `include` y un subsistema de contratos de funciones foraneas denominado **Externs**. Los archivos de externs describen la firma de las funciones de C para que el procesador semantico de Easy-C pueda validar llamadas, tipos de retorno y parametros antes de compilar.

---

## Especificacion Tecnica

### Sintaxis de Inclusion: Con y Sin Alias (`as`)

La directiva `include` admite dos modalidades con semanticas intencionalmente diferenciadas:

#### 1. Inclusion sin Alias (Inclusion Simple)
```easy-c
include "stdio"
include "stdlib"
```
* **Comportamiento en C:** Agrega la directiva de preprocesador `#include <stdio.h>` o `#include <stdlib.h>` en la cabecera del archivo generado.
* **Comportamiento Semantico:** **No registra un espacio de nombres.** Ninguna funcion de la libreria queda expuesta para ser invocada mediante prefijo. Se utiliza cuando el programador solo necesita que la libreria este disponible en C para funciones del sistema o dependencias de bajo nivel.
* **Normalizacion:** La extension `.h` es redundante y se normaliza automaticamente (`"stdio.h"` -> `"stdio"`).

#### 2. Inclusion con Alias (Espacio de Nombres Cualificado)
```easy-c
include "stdlib" as C_STDLIB
include "stdio" as IO
```
* **Comportamiento en C:** Agrega la directiva `#include <stdlib.h>` en el archivo monolítico.
* **Comportamiento Semantico:** Registra un espacio de nombres activo (`C_STDLIB`). Los simbolos declarados en el archivo `.externs.egl` correspondiente pueden ser invocados mediante `C_STDLIB.malloc(...)` o `IO.puts(...)`.

---

## Formato de Archivos `.externs.egl`

Las firmas foraneas se definen en archivos con extension `.externs.egl` ubicados en `core/backend/<target>/externs/<nombre>.externs.egl`.

Sintaxis de firmas admitida:
```easy-c
ptr fopen(str filepath, str mode = "rb")
int fclose(ptr stream)
int fseek(ptr stream, int64 offset, int origin)
int64 ftell(ptr stream)
int fread(str buffer, int size, int count, ptr stream)
int puts(str s)
```

### Reglas de Declaracion de Externs:
1. **Tipo de Retorno:** Tipos nativos de EGL (`int`, `int64`, `str`, `ptr`, `void`).
2. **Parametros:** Cada parametro consta de `<tipo> <identificador>`.
3. **Parametros por Defecto:** Se admiten valores iniciales (ej. `= "rb"`).
4. **Punteros:** Los tipos `ptr` y `str` indican punteros nativos de C (`void*` y `char*`).

---

## Parser de Externs y Cache Binario

### Parser (`core/externs/parser.py`)
La funcion `parse_externs(file_path)` procesa el archivo de definiciones externas y extrae un diccionario de firmas con la estructura:

```python
{
    "fopen": {
        "return_type": "ptr",
        "is_pointer": True,
        "params": [
            {"type": "str", "name": "filepath", "has_default": False, "default": None},
            {"type": "str", "name": "mode", "has_default": True, "default": "rb"}
        ]
    }
}
```

### Cache Binario (`core/externs/cache.py`)
Para acelerar la compilacion en proyectos con multiples inclusiones, el sistema compila las firmas a un archivo binario `.cache` adyacente al `.externs.egl`:
* Al invocar `load_cached_symbols(file_path)`, compara la fecha de modificacion (`st_mtime`) del archivo `.cache` frente al `.externs.egl`.
* Si el cache es valido y reciente, carga directamente las firmas serializadas evitando reanalizar la sintaxis.
* Si el archivo fuente fue modificado, `save_cached_symbols` actualiza el cache binario.

---

## Validacion de Contratos en Tiempo de Compilacion (`ExternsManager`)

Cuando el codigo EGL realiza una llamada cualificada (ej. `IO.puts("Hola Mundo")`), el nodo `EGL_METHOD_CALL` es validado por `manager.validate_call(ns_name, symbol, args)` en `core/externs/manager.py`:

1. **Existencia del Namespace:** Verifica que `IO` haya sido incluido formalmente mediante `include "stdio" as IO`.
2. **Existencia del Simbolo:** Comprueba que `puts` forme parte del diccionario de firmas de esa libreria.
3. **Conteo de Argumentos Minimos:** Calcula los argumentos obligatorios (aquellos sin valor por defecto). Si la llamada provee menos argumentos, lanza:
   ```
   RuntimeError: Llamada a 'IO.puts' requiere al menos 1 argumentos, pero recibió 0
   ```
4. **Conteo de Argumentos Maximos:** Si se suministran mas argumentos de los declarados en la firma, lanza:
   ```
   RuntimeError: Llamada a 'IO.puts' recibe máximo 1 argumentos, pero recibió 2
   ```
5. **Retorno de Metadatos:** Suministra el tipo de retorno exacto de la funcion foranea (`returntype`) para que el backend C infiera correctamente el tipo de la variable que recibe el resultado.
