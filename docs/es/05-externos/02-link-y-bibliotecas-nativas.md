# 02. Enlace de bibliotecas nativas

`#link` añade una carpeta de búsqueda para el enlazador. Solo puede aparecer
en el módulo de entrada del proyecto:

```bg
#link "vendor/SDL3/bins"
#link "vendor/runtime/bins"

extern windows "SDL3":
    SDL_Init(flags: uint32) int32
```

Las rutas son relativas al proyecto, deben existir y no pueden escapar de él.
El compilador conserva los directorios por dominio y el backend los incorpora
al enlace final. Una biblioteca externa se registra junto con su dominio, por
ejemplo `windows:SDL3` o `c:ucrt`.

Los nombres pueden escribirse con extensiones nativas (`.lib`, `.dll`, `.a` o
`.so`) y con el prefijo `lib`; el resolver normaliza esos detalles para buscar
la biblioteca adecuada al target.

Una declaración externa no copia código a Bagron: solo aporta el contrato que
usa el generador LLVM. La implementación, los símbolos exportados y la
compatibilidad de arquitectura siguen siendo responsabilidad de la biblioteca.
