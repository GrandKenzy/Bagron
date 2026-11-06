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

## Literales designados

Un `struct` puede construirse en una sola operación con los campos que se
quieran especificar. Los omitidos quedan en cero y el orden es libre:

```bg
point: Header = Header{
    .length = 128,
    .version = 1,
}
```

El literal conserva las lecturas postfix, por ejemplo `Header{ .version = 1,
.length = 128 }.length`. Es un temporal: sus campos no pueden ser destino de
asignación ni de `$`.
