# Pending: hardening de `volatile` y `opaque`

Estado: sin pendientes activos en este alcance.

Fecha de cierre: 2026-11-14

## Decisiones aplicadas

- `volatile mold` propaga el calificador al store del miembro activo y al
  store de limpieza del temporal; las lecturas y escrituras observables siguen
  usando operaciones LLVM volátiles.
- Una función Bagron `@consume` recibe los parámetros `opaque` como `owned` y
  debe cerrarlos o transferirlos antes de cada retorno, llamada `Never` o salida
  normal. El diagnóstico identifica el parámetro y su estado final.
- El consumo de un descriptor `opaque` global se rechaza; los movimientos
  siguen limitados a ownership local para evitar dobles cierres entre funciones.
- `@consume` aplica a todos los parámetros `opaque` directos de la función. La
  implementación y las regresiones verifican que todos queden descargados.
- `handle: FD` conserva el estado inicial `owned`: el cero de la representación
  es un handle nulo válido para esta etapa y no se introduce un estado runtime
  adicional.
- Se verificaron las rutas ABI de `opaque`, las restricciones de uso, módulos y
  la documentación visible sin añadir metadata de ownership al ABI.

## Verificación

- Las regresiones rápidas de ownership y las pruebas agresivas de backend,
  ABI, miembros y límites de ownership cubren este cierre.
- `tests/` conserva las pruebas rápidas; `tests_aggressive/` conserva las
  pruebas de backend, ABI y casos adversariales.

## Fuera de este pending

- `volatile_ref` o un tipo `mmio<T>`.
- Operaciones atómicas y fences.
- Bloques `unsafe` locales.
- Rediseño general del borrow checker.
- Retirada inmediata de la convención legacy `close_*`.
