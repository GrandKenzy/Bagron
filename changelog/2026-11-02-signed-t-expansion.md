# Nuevo metadato expansivo `Signed_t`

Bagron admite `Signed_t` en firmas internas. El compilador lo genera en la
llamada sin que el usuario lo escriba:

```bg
func consume(data: int32[], length: Len_t, size: Size_t, sign: Signed_t) void:
    return
```

El valor expandido es `0` para tipos signed y `1` para tipos no signed. El
metadato es opcional y, cuando se declara para un array, debe seguir a
`Size_t`.
