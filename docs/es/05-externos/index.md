# ABI y declaraciones externas

## Índice

- [01. Dominios y firmas ABI](01-dominios-y-firmas-abi.md)
- [02. Enlace de bibliotecas nativas](02-link-y-bibliotecas-nativas.md)
- [03. Punteros y descriptores opacos](03-punteros-y-opaque.md)
- [04. Restricciones y diagnósticos](04-restricciones-y-diagnosticos.md)

`extern` declara una firma que existe fuera de Bagron y registra la biblioteca
con su dominio de target:

```bg
clause System 'windows'
clause Arch 'amd'

extern windows "kernel32":
    GetStdHandle(kind: uint32) *: void
```

Los dominios actuales son `windows` y `c`. Deben ser compatibles con `System`;
ningún dominio externo se permite en `baremetal`.

Una firma externa puede usar escalares, `void*`, punteros tipados y agregados
compatibles con la ABI. No puede recibir arrays, `chain`, `buffer` derivado ni
`Len_t`/`Size_t`.

## Directorios locales

Solo el módulo de entrada puede añadir directorios de enlace:

```bg
#link "./bins"
#link "vendor/SDL3/bins"

extern windows "SDL3":
    SDL_Init(flags: uint32) int32
```

Las rutas deben existir y quedar dentro del proyecto. El compilador valida
la existencia de la ruta y resuelve la biblioteca nativa correspondiente según el
target y la convención ABI activa.

## Descriptores `opaque`

```bg
opaque HANDLE: void*

extern windows "kernel32":
    GetStdHandle(kind: uint32) HANDLE
```

Un descriptor `opaque` solo coincide con otro descriptor del mismo nombre. No
se puede desreferenciar, indexar, convertir ni comparar como puntero común.
