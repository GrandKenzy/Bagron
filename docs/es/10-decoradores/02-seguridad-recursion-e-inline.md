# 02. Seguridad, recursión e `inline`

## `@unsafe`

`@unsafe` abre una frontera explícita para operaciones cuya procedencia o
límites no puede demostrar el compilador:

```bg
@unsafe
func write(pointer *: int32, value: int32) void:
    (pointer) = value
    return
```

Una función segura no puede llamar a una `@unsafe`. El decorador no valida la
dirección, no convierte `Null` en una dirección válida y no elimina las reglas
de tipos, arrays, `buffer` o datos expansivos.

## `@recursive`

La recursión directa de cola se convierte automáticamente en un bucle cuando
la función cumple las condiciones del backend:

```bg
func countdown(value: int32) int32:
    if value == 0:
        return 0
    return countdown(value - 1)
```

Una recursión que no es una llamada de cola, o un ciclo entre varias funciones,
requiere marcar con `@recursive` todas las funciones del ciclo:

```bg
@recursive
func factorial(value: int32) int32:
    if value == 0:
        return 1
    return value * factorial(value - 1)
```

El decorador declara que el ciclo es intencional; no convierte una recursión no
acotada en una operación segura ni garantiza que no agote la pila.

## `inline`

`inline` se escribe en la firma:

```bg
inline func twice(value: int32) int32:
    return value + value
```

En perfiles `prod` y `high` solicita `alwaysinline`; en `dev` conserva una
`inlinehint` visible en el IR. No se aplica a funciones externas ni a cuerpos
de ensamblador.
