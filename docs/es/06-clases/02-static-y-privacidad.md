# 02. Métodos estáticos y miembros privados

Un método `@static` no recibe `self` y se invoca mediante el nombre de la
clase:

```bg
class Math:
    pass

    @static
    func twice(value: int32) int32:
        return value + value

func main() int32:
    return Math.twice(21)
```

Los nombres de campos y métodos que empiezan por `_` son privados para la
clase que los declara. El código de la propia clase puede usarlos:

```bg
class Account:
    func __init__(value: int32) void:
        self._balance = value

    func _close() int32:
        return self._balance
```

Un consumidor externo no puede leer `_balance` ni llamar a `_close`. La
subclase tampoco obtiene acceso a los miembros privados declarados por su
padre; expón un método público cuando la subclase necesite esa operación.
