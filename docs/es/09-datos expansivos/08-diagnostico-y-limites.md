# 08. Diagnóstico y límites

Los tipos expansivos retirados no son aliases de compatibilidad. Esta
declaración produce un diagnóstico:

```bg
func old(values: int32[], length: Len_t) void:
    pass
```

Debe escribirse:

```bg
func current(values: int32[]) usize:
    return values.<len>
```

También se diagnostican `value.len`, miembros de compilador desconocidos y el
uso de `.<len>` sobre escalares o punteros crudos. `.<size>` no aplica a
`chain` ni `buffer`, y `.<region>` solo es una consulta simbólica de
procedencia conocida.

Los miembros de compilador son de solo lectura y no sustituyen a los campos
de un tipo nominal.
