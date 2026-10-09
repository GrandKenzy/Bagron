# Sistema de Modulos y Mangling

Easy-C (EGL) cuenta con un sistema de modulos estricto que permite descomponer aplicaciones en unidades de compilacion desacopladas. Para evitar conflictos de nombres al consolidar todos los modulos en un unico archivo monolitico de C (`program.c`), el compilador implementa una tecnica determinista de *Name Mangling* y reescritura de llamadas en el AST.

---

## Especificacion Tecnica

### Ubicacion y Estructura de Modulos

Los modulos deben residir obligatoriamente en la carpeta `modules/` dentro del arbol fuente del proyecto:

```
source/
├── main.egl
└── modules/
    ├── utilidades.egl
    └── matematicas.egl
```

Para importar un modulo desde `main.egl` u otro modulo, se utiliza la sentencia `import`:

```easy-c
import matematicas
import utilidades as Utils
```

El resolvedor de archivos en `core/compiler.py` busca el modulo bajo el siguiente orden de precedencia:
1. `source_dir / 'modules' / f'{mod_name}.egl'`
2. `source_dir / f'{mod_name}.egl'`
3. Si no existe en ninguna de las rutas, detiene la compilacion con `FileNotFoundError`.

### Verificacion Estricta de la Clausula `Target`

Easy-C exige que el target del backend sea coherente en todo el proyecto. Si un modulo declara una clausula `Target` que difiere del target del archivo `main.egl`, el compilador aborta el proceso:

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
3. **Mapeo de Simbolos:**
   * El compilador registra en `all_mangled_symbols` tres formas de acceso:
     * Nombre cualificado con modulo: `miModulo.saludar` -> `inmodule_miModulo_saludar`
     * Nombre cualificado con alias (si aplica): `MM.saludar` -> `inmodule_miModulo_saludar`
     * Nombre directo del simbolo: `saludar` -> `inmodule_miModulo_saludar`

---

## Reescritura de Llamadas (`rewrite_mangled_calls`)

Tras recopilar el mapa completo de simbolos con mangling de todos los modulos dependientes, el compilador ejecuta una pasada sobre el AST de cada modulo y sobre el AST de `main.egl` antes de ingresarlos al procesador semantico:

* **Llamadas Directas (`EGL_CALL`):** Si un nodo `call` invoca un identificador presente en el mapa (ej. `saludar(21)`), el valor del token en `node.tokens` se reescribe inmediatamente al nombre mangled (`inmodule_miModulo_saludar(21)`).
* **Llamadas Cualificadas (`EGL_METHOD_CALL`):** Si el AST contiene una invocacion del tipo `miModulo.saludar(21)`, el nodo se transforma estructuralmente a un nodo `EGL_CALL` directo con el simbolo `inmodule_miModulo_saludar`, preservando la lista de argumentos `EGL_ARGUMENTS`.

---

## Ejemplo Completo de Transformacion

Modulo `source/modules/operaciones.egl`:
```easy-c
clause Target 'egl-c'

int calcular(int a, int b):
    return a + b
```

Archivo principal `source/main.egl`:
```easy-c
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
