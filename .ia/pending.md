# Pending: hardening de `volatile` y `opaque`

Estado: pendiente activo. La fase de baseline/checkpoint ya está cerrada y los
parámetros opaque de `@consume` ya entran como `owned`; todavía falta cerrar el
contrato completo de salida, la política de globals y la auditoría de
`volatile`.

Fecha de elaboración: 2026-11-14

## Objetivo

Reforzar la corrección de `volatile` y los contratos de ownership de `opaque`
sin convertir `volatile` en una garantía falsa de seguridad, sin introducir
todavía tipos MMIO nuevos, atomics, fences ni bloques `unsafe`.

La prioridad es `opaque`: su representación nominal y sus movimientos básicos
ya existen, pero los contratos de consumo todavía pueden ser demasiado
permisivos.

## Alcance congelado

- Mantener `volatile struct`, `volatile mold` y `volatile fields` tal como
  existen.
- No añadir `@volatile` ni un calificador volátil para variables, punteros o
  campos individuales.
- No usar `volatile` para resolver procedencia, límites, ownership,
  atomicidad, memory ordering o carreras.
- Mantener `close_*` como compatibilidad legacy hasta una decisión explícita;
  no retirarlo silenciosamente.
- Mantener el ABI actual de `opaque`: entero escalar o `void*`, sin tags
  runtime.
- Preservar los cambios locales ajenos que ya existan en el workspace.

## Hallazgos que motivan el trabajo

### `volatile`

El flujo actual es correcto: la gramática registra el calificador en el
`AggregateSymbol`, el registro LLVM lo consulta y `_MemoryPlace` lo propaga a
`load volatile` y `store volatile`. Las pruebas de backend ya cubren `struct`,
`mold`, `fields`, punteros y el pipeline `prod`.

Existe un punto que requiere una prueba específica: al emitir un literal de
`volatile mold`, el backend limpia el temporal con un store volátil, pero el
store posterior del miembro activo no pasa explícitamente `volatile=True`. No
se debe corregir hasta confirmar si ese temporal puede representar memoria
observable.

### `opaque`

La representación es nominal y no se puede envolver en punteros ni arrays.
Ownership se analiza solo en frontend y no se añade al ABI runtime.

Los principales riesgos pendientes son:

1. Una función `@consume` recibe parámetros opaque como `owned`, pero el
   análisis de fugas solo revisa bindings locales. Una función Bagron puede
   aceptar un descriptor y salir sin cerrarlo ni transferirlo.
2. Debe auditarse si un descriptor global puede consumirse desde más de una
   función. La transferencia global ya se rechaza, pero el consumo necesita la
   misma política.
3. `@consume` aplica actualmente a todos los argumentos opaque de la función,
   no a parámetros individuales.
4. Una declaración local `handle: FD` recibe estado `owned` aunque su valor
   runtime sea el cero de la representación. Decidir si eso significa un
   handle nulo válido o un descriptor no inicializado es una decisión de
   compatibilidad separada.

## Plan por fases

### Fase 1: regresiones de `volatile`

- Añadir pruebas de accesos directos, globals, parámetros, arrays de agregados
  volátiles y `mold`.
- Verificar `dev`, `prod` y `high` cuando corresponda.
- Añadir una prueba de literal `volatile mold` y revisar el IR resultante.
- Corregir únicamente la propagación confirmada como incorrecta.
- Si no aparece una diferencia observable, conservar el backend sin cambios.

Criterio de salida: todas las lecturas y escrituras observables siguen siendo
`load volatile`/`store volatile` y no cambia la sintaxis.

### Fase 2: contrato de salida de `@consume`

- Exigir que cada uno termine `closed` o `moved` en todas las rutas de salida.
- Analizar retornos tempranos, `if`/`else`, bucles y llamadas `Never`.
- Emitir un diagnóstico específico para cada parámetro no consumido.
- Mantener los `extern` como contratos confiables porque su cuerpo no se puede
  analizar.

### Fase 3: política de globals opaque

- Añadir pruebas de consumo y transferencia desde globals en varias funciones.
- Confirmar si el estado se comparte correctamente entre funciones.
- Recomendación: un global opaque debe ser `borrowed` o no consumible, salvo
  una API explícita de transferencia global.
- Rechazar cualquier consumo que pueda permitir cerrar dos veces el mismo
  recurso lógico desde funciones distintas.

### Fase 4: múltiples parámetros opaque

- Probar `@consume` con uno, dos y más parámetros opaque.
- Documentar que la semántica actual consume todos o detectar el caso como
  contrato ambiguo.
- Recomendación futura: ownership por parámetro.
- No introducir sintaxis nueva en esta fase sin una decisión explícita.

### Fase 5: validez inicial del descriptor

Auditar el comportamiento de:

```bg
handle: FD
```

Opciones a evaluar:

- exigir inicialización desde una función creadora;
- introducir estado `invalid`/`uninitialized`;
- conservar cero como handle nulo válido.

Esta fase es opcional y separada porque puede romper código existente y no
debe mezclarse con la corrección de `@consume`.

### Fase 6: ABI, módulos y documentación

- Verificar `opaque` entero en targets tipo Linux.
- Verificar `opaque void*` y ABI de Windows.
- Verificar imports, paquetes `.lib`, tipos nominales y firmas `extern`.
- Confirmar que siguen rechazados `opaque*`, arrays, `$handle` y conversiones
  de representación.
- Actualizar `docs/` solo con reglas visibles para usuarios.
- Añadir cambios visibles únicamente al changelog de la versión más reciente
  en desarrollo, escrito en inglés.
- Actualizar `.ia/map/README.md` solo si cambian responsabilidades o conexiones
  arquitectónicas.

## Criterios de aceptación

- `volatile` conserva su significado actual y no se usa como sustituto de
  seguridad de punteros o atomics.
- Una función Bagron `@consume` no puede abandonar un descriptor propio sin
  cerrarlo o transferirlo.
- Los globals opaque no pueden provocar ownership duplicado.
- Los diagnósticos distinguen `borrowed`, `moved`, `closed` y consumo incompleto.
- El ABI generado no incorpora metadata de ownership ni tags runtime.
- Las pruebas rápidas permanecen en `tests/` y las validaciones de backend/ABI
  en `tests/aggressive/`.
- Se ejecutan solo las pruebas pertinentes y se informa cualquier grupo no
  ejecutado.

## Fuera de este pending

- `volatile_ref` o un tipo `mmio<T>`.
- Operaciones atómicas y fences.
- Bloques `unsafe` locales.
- Rediseño general del borrow checker.
- Retirada inmediata de la convención legacy `close_*`.
