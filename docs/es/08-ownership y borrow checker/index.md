# Ownership estático y préstamos

## Índice

- [01. Estados de `buffer`](01-estados-de-buffer.md)
- [02. `unique` y `Region_t`](02-unique-y-region.md)
- [03. Descriptores `opaque`](03-opaque-y-cierre.md)
- [04. `@unsafe` y la frontera de punteros](04-unsafe-y-punteros.md)
- [05. Alcance real del borrow checker](05-alcance-del-borrow-checker.md)

Bagron no tiene un recolector de basura ni un runtime que rastree ownership.
El compilador mantiene estados estáticos para `buffer` y descriptores `opaque`.
Estos estados no se almacenan en el ejecutable: sirven para diagnosticar
movimientos, préstamos, cierres y fugas durante la compilación.

## Qué es un handler en Bagron

En código de sistema, un *handler* es un valor que identifica un recurso
externo —por ejemplo un archivo, socket, evento o mapeo— y que debe cerrarse
exactamente una vez. En Bagron, el tipo apropiado suele ser un descriptor
`opaque`, no un entero ni un puntero público:

```bg
opaque HANDLE: void*
```

`opaque` solo define el nombre nominal y su representación ABI para la
biblioteca que lo declara. El usuario puede recibirlo, devolverlo, pasarlo y
compararlo según las reglas del tipo, pero no puede desreferenciarlo,
indexarlo, convertirlo a entero o mezclarlo con otro `opaque` incompatible.
Bagron tampoco sabe si el valor sigue siendo válido en el sistema operativo;
esa responsabilidad pertenece a la biblioteca que adquiere y libera el
recurso.

No todo `opaque` es necesariamente un handle de Windows ni todo handle nativo
debe exponerse como `opaque`: el contrato depende de la API. Lo importante es
que el recurso tenga una operación de cierre y que esa operación se declare
como consumidora.

## Estados de `buffer`

```bg
func main() int32:
    data: buffer[4] = 0
    data[0] = 7
    Del data
    return 0
```

Un buffer local empieza como `owned`. `Del` lo lleva a `dead`; cualquier uso
posterior es un error de compilación. Un parámetro `buffer[]` es `borrowed`: se
puede leer y modificar, pero la función receptora no puede liberarlo.

```bg
func fill(data: buffer[], length: Len_t) void:
    if length > 0:
        data[0] = 1
    return
```

El ownership permanece en el llamador. `buffer` no es `byte[N]`: el primero usa
reserva dinámica; el segundo es un array estático.

## Exclusividad con `unique`

```bg
func transform(
    data: unique buffer[],
    length: Len_t,
    region: Region_t
) void:
    return
```

`Region_t` es oculto en la llamada y solo se acepta cuando el compilador puede
demostrar una procedencia exclusiva. El contrato también se aplica a arrays
`unique T[]`; no cambia las reglas de los punteros crudos.

`$value` obtiene una dirección, pero el puntero no mantiene vivo el objeto ni
puede retornarse desde una función. Para verificar fugas de recursos locales en compilación, el compilador admite
la opción `--strict-ownership` (por ejemplo `bagron --strict-ownership archivo.bg`).
