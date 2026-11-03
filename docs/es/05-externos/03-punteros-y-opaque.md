# 03. Punteros y descriptores opacos

Usa punteros tipados cuando la ABI conoce el dato apuntado y `void*` cuando la
biblioteca entrega una dirección sin tipo útil para Bagron:

```bg
extern c "ucrt":
    memcpy(destination *: void, source *: void, bytes: uint64) *: void
```

Un `opaque` nombra un descriptor cuyo layout pertenece a la biblioteca:

```bg
opaque HANDLE: void*

extern windows "kernel32":
    GetStdHandle(kind: uint32) HANDLE
```

El descriptor se puede recibir, devolver y comparar por identidad de tipo,
pero Bagron no permite desreferenciarlo, indexarlo ni tratarlo como un puntero
común. Esto conserva el límite entre el layout privado de la biblioteca y el
código fuente.

No conviertas un `opaque` en un agregado local para acceder a sus campos. Si la
API ofrece operaciones sobre el recurso, declara esas operaciones como más
funciones `extern` y conserva el descriptor entre llamadas.
