# 04. Métodos y clases

## `@static`

`@static` solo se permite en métodos de clase. El método no recibe `self` y se
llama usando el tipo:

```bg
class Math:
    pass

    @static
    func twice(value: int32) int32:
        return value + value

func main() int32:
    return Math.twice(21)
```

Los métodos mágicos (`__eq__`, `__ongetter__`, `__onsetter__`,
`__deletion__` y operadores) no pueden ser `@static`, porque necesitan el
receptor implícito o una semántica de instancia.

## `@after`

`@after` solo se aplica a `__ongetter__` y `__onsetter__`. Cambia el momento
del hook: se ejecuta después de leer o escribir el atributo:

```bg
class Counter:
    func __init__(value: int32) void:
        self.value = value

    @after
    func __onsetter__(name: chain, length: Len_t) int32:
        return 1
```

El hook conserva su firma reservada: recibe el nombre como `chain` y su
`Len_t`, y devuelve `int32` (`1` permite la operación y `0` la detiene).
`@after` no puede ponerse en un método ordinario ni en otro hook mágico.

## `@before`

`@before` solo se aplica al método mágico de ciclo de vida `__deletion__`. Hace
que el hook se ejecute **antes** de que `Del instance` limpie a cero la memoria
de la instancia, permitiendo leer sus campos originales:

```bg
class FileHandle:
    func __init__(handle: uint64) void:
        self.handle = handle

    @before
    func __deletion__() void:
        if self.handle != 0:
            self.handle = 0
```

Sin `@before`, `__deletion__` se ejecuta por defecto **después** de la limpieza
automática a cero de la instancia. `@before` no puede usarse en métodos
ordinarios ni en otros hooks.

## `@frozen`

`@frozen` se aplica a una clase, no a cada método:

```bg
@frozen
class Point:
    func __init__(x: int32) void:
        self.x = x

    func read() int32:
        return self.x
```

Sus atributos solo pueden escribirse durante `__init__` o `__frontend__`. Una
subclase de una clase `@frozen` también debe ser `@frozen`; la regla no puede
reabrirse desde la hija. El iniciador puede ser `@unsafe`, pero no admite otros
decoradores.
