# 02. `mold` y reinterpretación

`mold` permite describir varias vistas de una misma región:

```bg
mold WordView:
    whole: uint32
    bytes: byte[4]

func first_byte(value: WordView) byte:
    return value.bytes[0]
```

Los campos comparten almacenamiento. Escribir `whole` y leer después `bytes`
reinterpreta los mismos bits; no es una conversión de tipos ni una copia.

Si un campo contiene una dirección, la procedencia obtenida al leerla no queda
demostrada por el compilador. Desreferenciar ese puntero requiere una función
`@unsafe` y un contrato explícito sobre la validez de la dirección:

```bg
mold PointerBits:
    address *: uint8

@unsafe
func read_address(value: PointerBits) uint8:
    return (value.address)
```

Usa `mold` para formatos binarios y registros compatibles, no para simular
conversiones seguras entre tipos no relacionados.

Un literal de `mold` selecciona exactamente una vista activa:

```bg
view: WordView = WordView{ .whole = 270544960 }
```

No se permiten varios campos ni un literal vacío, porque los miembros se
superponen en la misma región de almacenamiento.
