# Perfiles de optimización LLVM y bucles SSA

Bagron incorpora la cláusula de entrada `Optimizations` con tres perfiles:

```bg
clause Optimizations 'dev'  ; IR de diagnóstico
clause Optimizations 'prod' ; predeterminado
clause Optimizations 'high' ; optimización local más intensa
```

`prod` y `high` verifican y optimizan el IR antes de publicar el `.ll` y
generar el objeto. Los agregados grandes conservan su almacenamiento, pero sus
escalares vecinos sí pasan por la promoción segura de SROA. La inicialización
cero de arrays grandes se emite como `memset` para no expandirla en miles de
stores durante esa promoción.

`Len_t` y `Size_t` son inmutables y se emiten directamente desde sus argumentos
del ABI, de modo que no necesitan `alloca` ni cargas repetidas.

Los iteradores de `for` que no usan `$iterador` se emiten como `phi` SSA en
los perfiles optimizados. Si se toma su dirección, Bagron conserva el
almacenamiento direccionable para mantener la semántica de punteros.

El benchmark `examples/canon/benchmark_redirect.bg` y su referencia C ahora
varían el valor serializado, consumen el buffer fuera de la ventana medida y
reportan mínimo y mediana en ticks. Las cifras antiguas en microsegundos se
mantienen como referencia histórica porque el protocolo de medición cambió.

Rutas relacionadas: `core/backend/llvm/`, `core/frontend/processor/`,
`examples/canon/benchmark_redirect.*`, `docs/es/02-Básico/07-Módulos e Imports.md`.
