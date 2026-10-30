# Referencia Rust para el benchmark de redireccion

Se añadió `examples/canon/benchmark_redirect.rs`, una referencia Win32 sin
crates externos. Usa el mismo protocolo que Bagron y C: `QueryPerformanceCounter`,
cinco rondas de calentamiento, diez muestras, mil iteraciones y consumo del
buffer fuera de la ventana medida.

En una serie local de ejecuciones:

| Implementación | Configuración | Buffer, mediana aproximada |
| --- | --- | ---: |
| Bagron | `prod` | 656--743 ticks |
| Rust | `rustc -C opt-level=3` | 333--436 ticks |
| C | `clang -O2` | 390--936 ticks |

Los ticks de archivo son muy variables por `WriteFile`; no se usan como
umbral. Rust optimizado queda en la misma escala que C optimizado. La brecha
restante de Bagron en buffer procede de la construcción de un registro temporal
y de la copia byte a byte; el siguiente objetivo es emitir serialización directa
y copias contiguas equivalentes a `memcpy` sin debilitar las garantías de
`unique`.
