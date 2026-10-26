# Backend LLVM

El backend actual consume los símbolos semánticos producidos por
`core/frontend` y no vuelve a interpretar el AST ni la sintaxis antigua.

## Primera etapa

La primera etapa genera `build/<modulo>.ll`, `build/<modulo>.obj` y
`build/<modulo>.exe` para:

- variables globales escalares;
- enteros de ancho fijo `Bint<n>` y `uBint<n>`;
- booleanos y números de punto flotante;
- arrays globales inicializados con literales;
- referencias a globals `const` que puedan plegarse estáticamente.
- `main() bool` como función interna LLVM `i1` y wrapper nativo `main() i32`.

Los globals sin inicializador escalar se emiten con valor cero. Las referencias
a globals mutables, ciclos de inicialización, `callptr`, cadenas y estructuras
quedan fuera de esta primera emisión. Las variables locales y los parámetros ya
se registran y validan en el frontend, pero todavía no generan instrucciones
LLVM. El wrapper nativo convierte `true` en código de salida `0` y `false` en
`1`.

## Inicialización de LLVM

EasyC usa `llvmlite` desde el entorno gestionado por vnma. El backend inicializa
los registros de targets y el asm printer, crea un `ir.Module`, configura el
triple y el data layout, y finalmente verifica el texto mediante
`binding.parse_assembly(...).verify()`.

`Arch` acepta `auto` por defecto, además de `x86`, `amd`, `arm` o un triple LLVM.
`auto` usa la arquitectura del host. Un target que LLVM no pueda resolver es un
error; no se hace fallback silencioso.

## Limitaciones actuales

El ejecutable actual solo contiene el entrypoint mínimo y no traduce todavía
funciones auxiliares, variables locales, llamadas, clases ni control de flujo.
El backend no genera `program.c` ni headers C.
