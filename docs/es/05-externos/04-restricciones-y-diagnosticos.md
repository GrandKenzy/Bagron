# 04. Restricciones y diagnósticos

Estas formas se rechazan de manera intencionada:

```bg
extern "kernel32": Bad() int32       # falta el dominio
extern baremetal "firmware": Bad() int32
extern windows "kernel32": Bad(x: int32 = 0) int32
extern windows "kernel32": Bad(values: int32[]) int32
```

El dominio debe ser explícito y compatible con `System`. El backend necesita
una firma ABI fija, por eso no puede resolver defaults ni arrays dinámicos.
Tampoco puede exportarse `main` como símbolo externo ni repetirse el nombre de
un parámetro.

Si el compilador no encuentra la biblioteca, revisa primero el target, el
dominio, el nombre normalizado y los directorios `#link` del módulo de entrada.
Si encuentra la biblioteca pero rechaza la firma, sustituye tipos de metadatos
(`Len_t`, `Size_t`, etc.) por escalares ABI explícitos como `uint64`.
