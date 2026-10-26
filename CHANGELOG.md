# Changelog

Todos los cambios relevantes de EasyC/Bagron se documentan en este archivo.

## [Unreleased] - 2026-10-25

### Añadido

- Backend LLVM inicial en `core/backend/llvm`, usando `llvmlite` para generar y verificar módulos `.ll`.
- Emisión de variables globales escalares, arrays literales, `Bint<n>`, `uBint<n>` y referencias estáticas a globals `const`.
- Scopes `Storage` independientes por función para parámetros, variables locales y variables de iteración `ran`.
- Validación semántica inicial de tipos locales y retornos de funciones top-level.
- Requisito de una función global `main` como punto de entrada del módulo.
- Emisión LLVM inicial de `main() bool` como `__bagron_main() i1` más un wrapper nativo `main() i32`.
- Generación de objetos y ejecutables mínimos mediante `llvmlite` y Clang/LLD.
- Tipos enteros de ancho exacto `Bint<n>` y `uBint<n>`.
- Metadata semántica para ancho y signo de enteros parametrizados.
- Tipo callable `callptr` con registro de firmas de funciones.
- Acceso postfix encadenado para miembros, índices y llamadas.
- Soporte sintáctico para arrays mediante sufijos `[]`.
- Soporte de punteros por niveles mediante `*` y `**`.

### Cambiado

- El frontend principal queda organizado como Bagron en `core/frontend`.
- La sintaxis canónica usa `ran` como iterador numérico único para `for`.
- `@packed` reemplaza a `__packed__` como decorador.
- `import` reemplaza a `include` para módulos Bagron.
- Las constantes se declaran dentro del tipo, por ejemplo `edad: const int`.
- `vnma` utiliza la copia local editable de Gram en `~/Desktop/Gram`.
- `vnma` fija `llvmlite==0.50.0` como dependencia del backend inicial.
- El punto y coma permanece reservado para comentarios de línea.

### Retirado

- Keywords y tipos obsoletos `in`, `iter`, `index`, `ptr`, `cptr` y `array`.
- Frontends y estructuras antiguas de C, EASYC y headers.

### Verificación

- `vnma install` restaurado correctamente desde `vnma.lock`.
- `vnma run main.py examples/modern_example` ejecutado correctamente.
- El backend valida el IR con `binding.parse_assembly(...).verify()` antes de guardar `build/<modulo>.ll`.
- Compilación de módulos Python validada con `compileall`.
