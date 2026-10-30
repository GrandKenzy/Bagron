# Plan de optimizaciones agresivas

Este documento concentra el recorrido recomendado para reducir la diferencia
de rendimiento entre Bagron, C y Rust en el benchmark de redirección.

## Objetivo inmediato

Eliminar el registro temporal y la copia byte a byte de la ruta de buffer:

```text
build_record(record, value)
record -> output
```

debe aproximarse a:

```text
serialize_direct(output + output_position, value)
```

La optimización debe conservar las comprobaciones de rango, la semántica de
`unique`, `Region_t`, `Len_t` y `Size_t`, y la observabilidad completa del
buffer fuera de la ventana medida.

## Orden de revisión

### 1. Benchmark y referencias

- `examples/canon/benchmark_redirect.bg`
- `examples/canon/benchmark_redirect.c`
- `examples/canon/benchmark_redirect.rs`

Comparar siempre `prod`, C `-O2` y Rust `-O3`. Repetir varias ejecuciones: los
ticks de `WriteFile` tienen variación externa y no deben convertirse en un
umbral absoluto.

### 2. Emisión de funciones y valores

Archivo: `core/backend/llvm/functions/statements.py`

Revisar primero:

- `_prepare_values`: decidir qué valores son argumentos SSA y cuáles necesitan
  dirección.
- `_emit_local_declaration`: evitar temporales cuando el valor no escapa.
- `_emit_for`: conservar iteradores SSA y sus límites exclusivos.
- `_emit_large_zero_initialization`: mantener arrays grandes direccionables sin
  expandir su inicialización en stores individuales.

### 3. Memoria, índices y copias

Archivo: `core/backend/llvm/functions/expressions/memory.py`

Revisar:

- `_load_address` y `_store_address`;
- `_compile_place` y la emisión de GEP;
- `_buffer_data_and_length`;
- detección de regiones contiguas;
- conversión segura de ciclos de copia a `llvm.memcpy`.

Un `memcpy` solo debe emitirse cuando el origen, destino, longitud y ausencia
de solapamiento estén demostrados. `unique` puede aportar `noalias`; un array
normal no debe recibir ese atributo por inferencia.

### 4. Serialización y llamadas

Archivo: `core/backend/llvm/functions/expressions/calls.py`

Revisar:

- `_compile_forwarded_expansion`;
- `_compile_array_argument`;
- `_compile_length_argument`;
- `_compile_size_argument`;
- llamadas con `unique`, `Region_t` y punteros a arrays.

La serialización ideal escribe directamente en el destino y devuelve el número
de bytes escritos. No debe crear `digits[32]` salvo que la dirección del
temporal se escape o la API lo exija.

### 5. Pipeline LLVM

Archivos:

- `core/backend/llvm/module.py`
- `core/backend/llvm/functions/base.py`

Verificar en el IR antes y después de cada cambio:

- ausencia de llamadas a helpers marcados `inline` en rutas calientes;
- ausencia de `alloca` para escalares promovibles;
- presencia de `llvm.memcpy` cuando corresponda;
- conservación de `llvm.memset` para arrays grandes;
- supervivencia de `volatile`;
- `noalias` solo en parámetros demostrablemente `unique`.

No aplicar SROA completo sobre buffers grandes si la inicialización o la copia
pueden expandirse a miles de instrucciones. El agregado debe seguir en memoria;
solo sus escalares auxiliares deben promocionarse.

### 6. Invariantes semánticos

Archivos:

- `core/frontend/tools/function.py`
- `core/frontend/tools/types/calls.py`
- `core/frontend/objects/function.py`

Confirmar que las optimizaciones no alteren:

- la expansión obligatoria de `Len_t` y `Size_t`;
- la inmutabilidad de esos metadatos;
- la exigencia de `Region_t` para `unique`;
- la prohibición de buffers superpuestos en rutas `unique`;
- los límites de arrays y el límite exclusivo de `for`;
- `break`, `continue`, paso cero y prevención de desbordamiento.

## Pruebas obligatorias

- `tests_aggressive/test_backend.py`
- `tests/test_buffer.py`
- `tests/test_functions.py`
- `tests_aggressive/test_unsafe.py`
- `tests_aggressive/test_standard.py`

Añadir pruebas de IR cuando una optimización dependa de una propiedad concreta:

- el buffer grande conserva su `alloca`;
- `Len_t` y `Size_t` no crean slots en `prod`/`high`;
- una copia segura genera `memcpy`;
- una ruta con alias posible no recibe `noalias`;
- un iterador direccionable conserva su almacenamiento.

## Protocolo de validación

1. Ejecutar `vnma run main.py examples/canon/benchmark_redirect.bg`.
2. Ejecutar el binario Bagron varias veces.
3. Compilar C con `clang -O0` y `clang -O2`.
4. Compilar Rust con `rustc -C opt-level=0` y `rustc -C opt-level=3`.
5. Comparar mínimo y mediana de `control`, `buffer` y `file`.
6. Inspeccionar el `.ll` generado y, si hace falta, el ensamblador.
7. Ejecutar las pruebas rápidas y después `vnma test tests_aggressive`.

La meta de esta fase no es prometer una cifra fija: es que la ruta de buffer
se acerque reproduciblemente a C `-O2` y Rust `-O3` sin relajar la seguridad
del lenguaje.
