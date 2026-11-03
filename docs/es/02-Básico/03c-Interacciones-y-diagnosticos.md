# Interacciones y diagnósticos

Los calificadores no son intercambiables con decoradores ni con metadatos de
firma:

```bg
values: const int32[2] = {1, 2}
values[0] = 3                 # error: array constante

func inspect(data: unique int32[]) void:
    return                    # error: falta Len_t, Size_t y Region_t

@unsafe
func read(data: int32[]) void:
    return                    # error: @unsafe no omite expansión de arrays
```

Errores frecuentes:

- `const` delante de `chain`, `Len_t`, `Size_t`, `Signed_t` o `Region_t`;
- `unique` en un escalar, puntero crudo o tipo que no es array/buffer;
- `volatile` escrito como `@volatile`;
- `inline` escrito como `@inline`;
- `static` en una función global o en un método mágico;
- `public`/`private` usados como si fueran decoradores `@public`/`@private`.

`@unsafe`, `@frozen`, `@packed`, `@align(N)` y `@order_msb` pertenecen al
sistema de decoradores y tienen sus propias posiciones. Consulta
[Decoradores](../10-decoradores/index.md) para sus contratos y combinaciones.

Del mismo modo, `Len_t`, `Size_t`, `Signed_t` y `Region_t` son parámetros
expansivos: se declaran en una firma, pero el llamador no los proporciona
manualmente. Consulta [Datos expansivos](../09-datos%20expansivos/index.md)
para su orden y asociación.
