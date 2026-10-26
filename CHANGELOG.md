# Changelog

Todos los cambios relevantes de EasyC/Bagron se documentan en este archivo.

## [Unreleased] - 2026-10-25

### Añadido

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
- El punto y coma permanece reservado para comentarios de línea.

### Retirado

- Keywords y tipos obsoletos `in`, `iter`, `index`, `ptr`, `cptr` y `array`.
- Frontends y estructuras antiguas de C, EASYC y headers.

### Verificación

- `vnma install` restaurado correctamente desde `vnma.lock`.
- `vnma run main.py examples/modern_example` ejecutado correctamente.
- Compilación de módulos Python validada con `compileall`.
