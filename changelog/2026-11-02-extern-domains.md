# Dominios explícitos para `extern`

Las declaraciones externas separan ahora el dominio de la librería:

```bg
extern windows "kernel32":
    GetStdHandle(kind: uint32) *: void

extern c "ucrt":
    printf(format *: char) int32
```

`extern windows` requiere `System 'windows'`; `extern c` es válido en targets de
sistema; ningún `extern` es válido en `baremetal`. El registro de enlaces
conserva el dominio (`windows:kernel32`, `c:ucrt`) y el backend lo traduce al
nombre de librería que recibe el linker. Tras migrar los usos internos, la forma
legacy `extern "library":` se rechaza y la gramática la conserva únicamente
para emitir un diagnóstico claro.
