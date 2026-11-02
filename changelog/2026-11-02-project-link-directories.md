# Directorios locales para librerías nativas

El módulo principal puede declarar varias rutas de búsqueda con `#link`:

```bg
#link "./bins"

extern windows "SDL3":
    SDL_Init(flags: uint32) int32
```

Las rutas son relativas al archivo que contiene la directiva, se normalizan y
deben permanecer dentro del proyecto. Bagron las pasa al linker con `-L`,
valida las variantes compatibles con Windows o Linux y copia las bibliotecas
dinámicas encontradas junto al ejecutable en `build/`. Los módulos importados
no pueden añadir rutas de enlace. Las librerías del sistema continúan
resolviéndose por sus dominios `extern` sin requerir `#link`.
