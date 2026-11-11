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

Los nombres de campo no pueden repetirse. El cuerpo no puede quedar vacío y
los campos no pueden usar `chain` ni arrays abiertos; las dimensiones de un
array de campo deben ser estáticas. Un agregado no puede contenerse a sí mismo
por valor, directa o indirectamente, porque eso produciría un tamaño infinito.
La recursión mediante un puntero sí es válida:

```bg
struct Node:
    value: int32
    next *: Node
```

El layout conserva el orden declarativo de los campos. El backend puede añadir
padding para satisfacer la alineación natural; `@packed` y `@align(N)` cambian
ese layout y deben formar parte del contrato ABI si se usan.

## Campos de texto

Un campo `char` o `char[N]` se lee y se escribe igual que cualquier otro campo
del `struct`. El tipo no impide el acceso por formar parte de un agregado:

```bg
struct Text:
    first: char
    bytes: char[8]

func first_byte(value: Text) char:
    return value.bytes[0]
```

`char` contiene un byte. Si `bytes` almacena UTF-8, un carácter Unicode puede
ocupar varios elementos y debe procesarse como una secuencia de bytes. El acceso
a un `struct` local es directo; si se recibe un puntero al `struct`, la función
debe marcarse `@unsafe` porque el puntero no lleva límites:

```bg
@unsafe
func byte_at(value *: Text, index: usize) char:
    return (value).bytes[index]
```

`@unsafe` expresa la responsabilidad sobre la dirección y el índice; no bloquea
la lectura de campos `char` ni de arrays de `char`.

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
