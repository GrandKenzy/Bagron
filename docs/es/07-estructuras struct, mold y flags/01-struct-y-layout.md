# 01. `struct` y layout

`struct` declara un agregado con campos independientes y layout nominal:

```bg
struct Header:
    version: uint16
    length: uint32

func read_header(header: Header) uint32:
    return header.length
```

Los campos se almacenan por separado y se acceden con `header.version`.
Puedes obtener la dirección de un campo direccionable con `$header.version`:

```bg
@unsafe
func set_length(header *: Header, value: uint32) void:
    (header).length = value
```

El padding y la alineación siguen las reglas del backend salvo que se indique
un decorador de layout. Un `struct` no es un `mold`: leer un campo no
reinterpreta los bytes de otro campo.
