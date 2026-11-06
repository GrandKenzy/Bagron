# 03. `flags` y bitfields

`flags` empaqueta campos booleanos o bitfields dentro de un entero base:

```bg
flags Permissions uint8:
    read: uBint<1> = 0
    write: uBint<1> = 0
    reserved: uBint<6> = 0

func can_write(value: Permissions) bool:
    return value.write == 1
```

La suma de anchos debe coincidir exactamente con la base. Los campos pueden ser
`uBint<N>`, `Bint<N>` o `bool`; un campo no tiene dirección independiente, por
lo que `$value.write` es inválido.

El orden predeterminado es LSB. Para protocolos que numeran desde el extremo
más significativo se usa `@order_msb`:

```bg
@order_msb
flags NetworkBits uint8:
    version: uBint<3> = 0
    kind: uBint<5> = 0
```

`@order_lsb` no existe: era un alias redundante del valor predeterminado.

También puedes crear un valor de flags sin depender de los valores declarativos
del tipo. El literal designado empieza con todos los bits en cero y solo coloca
los campos escritos:

```bg
active: Permissions = Permissions{ .write = 1 }
```
