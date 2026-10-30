# Perfiles de optimización LLVM y bucles SSA

Bagron incorpora la cláusula de entrada `Optimizations` con tres perfiles:

```bg
clause Optimizations 'dev'  ; IR de diagnóstico
clause Optimizations 'prod' ; predeterminado
clause Optimizations 'high' ; optimización local más intensa
```

`prod` y `high` verifican y optimizan el IR antes de publicar el `.ll` y
generar el objeto. La secuencia evita la expansión desproporcionada de módulos
con buffers grandes: los agregados de más de 1024 elementos no pasan por SROA,
mientras que las demás funciones sí pueden promover escalares locales.

Los iteradores de `for` que no usan `$iterador` se emiten como `phi` SSA en
los perfiles optimizados. Si se toma su dirección, Bagron conserva el
almacenamiento direccionable para mantener la semántica de punteros.

El benchmark `examples/canon/benchmark_redirect.bg` y su referencia C ahora
varían el valor serializado, consumen el buffer fuera de la ventana medida y
reportan mínimo y mediana en ticks. Las cifras antiguas en microsegundos se
mantienen como referencia histórica porque el protocolo de medición cambió.

Rutas relacionadas: `core/backend/llvm/`, `core/frontend/processor/`,
`examples/canon/benchmark_redirect.*`, `docs/es/02-Básico/07-Módulos e Imports.md`.
