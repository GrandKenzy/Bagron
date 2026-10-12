# Sistema de Modulos y Mangling

EGL cuenta con un sistema de modulos estricto que permite descomponer aplicaciones en unidades de compilacion desacopladas. Para evitar conflictos de nombres al consolidar todos los modulos en un unico archivo monolitico de C (`program.c`), el compilador implementa una tecnica determinista de *Name Mangling* y reescritura de llamadas en el AST.

---

## Especificacion Tecnica

### Ubicacion y Resolucion de Modulos y Librerias

La sentencia `import` resuelve tanto modulos de usuario (`.egl`) como librerias del target activo (`.egl`):

```
source/
├── main.egl
├── modules/
│   ├── utilidades.egl
│   └── matematicas.egl
└── targets/
    └── c/
        └── libraries/
            └── red.egl
```

Para importar un modulo o libreria desde `main.egl` u otro modulo, se utiliza la sentencia `import`:

```egl
import matematicas
import standard
import red as Net
```

El resolvedor `find_module_file()` en `core/compiler.py` busca el archivo bajo el siguiente orden de precedencia:
1. `source_dir / 'modules' / f'{mod_name}.egl'` (Modulos de usuario en la carpeta `modules/`).
2. `source_dir / f'{mod_name}.egl'` (Modulos de usuario en la raiz del proyecto).
3. `source_dir / 'targets' / backend / 'libraries' / f'{mod_name}.egl'` (Librerias de target locales del proyecto).
4. `core/backend/<backend>/libraries/<mod_name>.egl` (Librerias de target base provistas por el compilador, ej. `standard.egl`, `os.egl`).
5. Si no existe en ninguna de las rutas, detiene la compilacion con `FileNotFoundError`.

### Verificacion Estricta de la Clausula `Target`

EGL exige que el target del backend sea coherente en todo el proyecto. Si un modulo declara una clausula `Target` que difiere del target del archivo `main.egl`, el compilador aborta el proceso:

```python
# Verificacion en core/compiler.py
mod_clauses = extract_clauses(mod_ast)
if 'Target' in mod_clauses and mod_clauses['Target'] != target:
    raise ValueError(f"El módulo '{mod_name}' tiene un Target ('{mod_clauses['Target']}') diferente al Target principal ('{target}').")
```

---

## Algoritmo de Name Mangling (`mangle_module_symbols`)

Durante la carga de cada modulo en `core/compiler.py`, los identificadores declarados se transforman para asegurar unicidad global:

1. **Funciones:**
   * Patron: `inmodule_<nombre_modulo>_<nombre_funcion>`
   * Ejemplo: La funcion `saludar` en `modules/miModulo.egl` se convierte en `inmodule_miModulo_saludar`.
2. **Clases:**
   * Patron: `inmodule_<nombre_modulo>_<nombre_clase>`
   * Ejemplo: La clase `Vector` en `modules/geometria.egl` se convierte en `inmodule_geometria_Vector`.
3. **Mapeo de Simbolos y Resolucion de Colisiones:**
   * El compilador registra en `all_mangled_symbols` las formas de acceso cualificado:
     * Nombre cualificado con modulo: `foo.calcular` -> `inmodule_foo_calcular`
     * Nombre cualificado con alias (si aplica): `Ops.calcular` -> `inmodule_operaciones_calcular`
   * **Aislamiento Interno:** Dentro del codigo de un modulo, cualquier llamada interna a sus propias funciones resuelve de forma prioritaria a sus propios simbolos mangled (`local_symbols`), garantizando que `foo` jamas invoque accidentalmente la funcion de `bar`.
   * **Deteccion de Ambiguedad:** Si multiples modulos exportan el mismo identificador (ej: `foo.calcular` y `bar.calcular`), el compilador detecta la colision. Invocar `calcular()` de manera no cualificada en `main.egl` genera un error sintactico explicito de ambiguedad, exigiendo usar la sintaxis cualificada (`foo.calcular()`) o la sentencia `declare` (ej: `declare foo.calcular as calcular`).

---

## Reescritura de Llamadas (`rewrite_mangled_calls`)

Tras recopilar el mapa completo de simbolos con mangling de todos los modulos dependientes, el compilador ejecuta una pasada sobre el AST de cada modulo y sobre el AST de `main.egl` antes de ingresarlos al procesador semantico:

* **Llamadas Directas (`EGL_CALL`):** Si un nodo `call` invoca un identificador local o unicamente exportado, se reescribe al nombre mangled correspondiente. Si el identificador es ambiguo y no fue declarado con `declare`, se detiene la compilacion con diagnostico de ambiguedad.
* **Llamadas Cualificadas (`EGL_METHOD_CALL`):** Si el AST contiene una invocacion del tipo `miModulo.saludar(21)`, el nodo se transforma estructuralmente a un nodo `EGL_CALL` directo con el simbolo `inmodule_miModulo_saludar`, preservando la lista de argumentos `EGL_ARGUMENTS`.

---

## Ejemplo Completo de Transformacion

Modulo `source/modules/operaciones.egl`:
```egl
clause Target 'egl-c'

int calcular(int a, int b):
    return a + b
```

Archivo principal `source/main.egl`:
```egl
clause Target 'egl-c'
include "stdio"
import operaciones as Ops

int res = Ops.calcular(10, 20)
print("Resultado:", res)
```

Codigo C generado en `program.c`:
```c
#include <stdio.h>
#include <stdint.h>

int64_t inmodule_operaciones_calcular(int64_t a, int64_t b);

int64_t inmodule_operaciones_calcular(int64_t a, int64_t b){
    return a + b;
}

int main(int argc, char** argv) {
    int64_t res = inmodule_operaciones_calcular(10, 20);
    printf("%s %lld\n", "Resultado:", res);
    return 0;
}
```
