# Interacciones y diagnósticos

Los calificadores no son intercambiables con decoradores ni con metadatos de
firma:

```bg
values: const int32[2] = {1, 2}
values[0] = 3                 # error: array constante

func inspect(data: unique int32[]) void:
    return

@unsafe
func read(data: int32[]) void:
    return                    # error: @unsafe no omite expansión de arrays
```

Errores frecuentes:

- `const` delante de un miembro del compilador;
- `unique` en un escalar, puntero crudo o tipo que no es array/buffer;
- `volatile` escrito como `@volatile`;
- `inline` escrito como `@inline`;
- `static` en una función global o en un método mágico;
- `public`/`private` usados como si fueran decoradores `@public`/`@private`.

`@unsafe`, `@frozen`, `@packed`, `@align(N)` y `@signed` pertenecen al
sistema de decoradores y tienen sus propias posiciones. Consulta
[Decoradores](../10-decoradores/index.md) para sus contratos y combinaciones.

Los antiguos tipos expansivos fueron retirados. Consulta [Miembros del
compilador](../09-datos%20expansivos/index.md) para la API `.<len>`, `.<size>`
y `.<region>`.
