# 04. Hooks y operadores

Las clases pueden definir hooks concretos para personalizar accesos y
comparación:

```bg
class Box:
    func __init__(value: int32) void:
        self.value = value

    func __eq__(other: Box) bool:
        return self.value == other.value

    func __ongetter__(name: chain, length: Len_t) int32:
        return 1

    func __onsetter__(name: chain, length: Len_t) int32:
        return 1
```

`__eq__() bool` define la igualdad de instancias. `__ongetter__` y
`__onsetter__` reciben el nombre como `chain` y su `Len_t`; devuelven `1` para
permitir el acceso y `0` para detenerlo. `@after` hace que el hook se ejecute
después de la operación en lugar de antes.

Declara solo los hooks que necesites. No son métodos genéricos: sus nombres,
parámetros y resultado tienen una semántica reservada por el frontend.
