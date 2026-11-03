# Datos expansivos de compilación

## Índice

- [01. Modelo y llamada visible](01-modelo-y-llamada-visible.md)
- [02. Arrays y matrices](02-arrays-y-matrices.md)
- [03. `chain` y `buffer`](03-chain-y-buffer.md)
- [04. `Signed_t` y tamaños](04-signed-y-tamanos.md)
- [05. Propagación entre funciones](05-propagacion.md)
- [06. `unique` y `Region_t`](06-unique-y-region.md)
- [07. ABI y backend](07-abi-y-backend.md)
- [08. Diagnóstico y límites](08-diagnostico-y-limites.md)

`Len_t`, `Size_t`, `Signed_t` y `Region_t` aparecen en firmas, pero el usuario
no escribe sus argumentos en la llamada. Bagron los calcula y los añade al ABI.

```bg
func inspect(
    data: int32[],
    length: Len_t,
    element_size: Size_t,
    signed: Signed_t
) void:
    return

func main() int32:
    values: int32[3] = {1, 2, 3}
    inspect(values)
    return 0
```

La llamada visible `inspect(values)` recibe internamente `3`, `4` y `0`:

- `Len_t`: elementos de la primera dimensión;
- `Size_t`: bytes de una unidad exterior (`int32[2][3]` produce `2` y `12`);
- `Signed_t`: `0` para signed y `1` para unsigned o `byte`.

Para cada array, `Len_t` y `Size_t` deben aparecer inmediatamente después del
parámetro y en ese orden. `Signed_t`, si existe, va detrás.

`chain` puede pedir `Len_t` e incluye el `NUL`; `buffer[]` también usa solo
`Len_t`, tomado del descriptor:

```bg
func inspect_buffer(data: buffer[], length: Len_t) usize:
    return length
```

`Region_t` acompaña a un parámetro `unique` y representa la región exclusiva
demostrada por el compilador. No se escribe nunca en la llamada.
