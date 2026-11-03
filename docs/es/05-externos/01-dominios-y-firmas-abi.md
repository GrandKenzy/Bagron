# 01. Dominios y firmas ABI

Una declaración `extern` describe una función que Bagron no implementa. El
dominio indica qué familia de ABI puede resolverla:

```bg
clause System 'windows'
clause Arch 'amd'

extern windows "kernel32":
    GetStdHandle(kind: uint32) *: void

extern c "ucrt":
    puts(text *: char) int32
```

Los dominios admitidos son `windows` y `c`. El primero requiere un target
Windows; el segundo representa una biblioteca con convención C. Una declaración
extern no puede usarse en un target `baremetal`.

La forma de una firma es la misma que la de una función, pero el resultado se
escribe después de los parámetros. El `*` delante de `: tipo` indica un
resultado puntero:

```bg
extern windows "kernel32":
    GetLastError() uint32
    GetStdHandle(kind: uint32) *: void
```

Se admiten escalares, `void*`, punteros tipados, agregados compatibles y
descriptores `opaque`. No se admiten parámetros por defecto, arrays, `chain`,
`callptr`, `Null`, `Len_t`, `Size_t`, `Signed_t` ni `Region_t` en una firma
externa.
