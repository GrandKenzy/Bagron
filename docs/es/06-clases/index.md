# Clases

## Índice

- [01. Construcción y métodos](01-construccion-y-metodos.md)
- [02. Métodos estáticos y miembros privados](02-static-y-privacidad.md)
- [03. Herencia estática](03-herencia-estatica.md)
- [04. Hooks y operadores](04-hooks-y-operadores.md)
- [05. `@frozen` y destrucción](05-frozen-y-destruccion.md)

Las clases son agregados nominales con métodos resueltos en compilación. No
usan vtables ni estado de herencia en runtime.

```bg
class Point:
    func __init__(x: int32, y: int32) void:
        self.x = x
        self.y = y

    func total() int32:
        return self.x + self.y

func main() int32:
    point: Point = Point(2, 3)
    return point.total()
```

Una clase construible debe tener exactamente un iniciador: `__init__` para
construcción normal o `__frontend__` para aceptar una conversión de frontend.
Los métodos de instancia reciben `self` implícitamente.

## Métodos estáticos y herencia

```bg
class Math:
    pass

    @static
    func twice(value: int32) int32:
        return value + value

class Child(Point):
    func __init__(value: int32) void:
        super.__init__(value, value)
```

Un método `@static` se llama mediante la clase. La herencia es simple y
estática: la hija llama explícitamente a `super.__init__` y los campos se
aplanan en el layout.

`__eq__() bool` controla una instancia usada como condición. Los hooks
`__ongetter__` y `__onsetter__` reciben el nombre como `chain` y su `Len_t`;
devuelven `1` para permitir el acceso y `0` para detenerlo. `@after` los mueve
después de la operación.

`Del instance` limpia a cero automáticamente toda la memoria de la instancia.
Si existe `__deletion__`, se ejecuta por defecto después de la limpieza a cero
(o antes si está decorado con `@before`). `@frozen` limita las escrituras de
atributos a `__init__` o `__frontend__` y se propaga por herencia.
