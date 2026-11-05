# Control y funciones

## Cuerpos de función en una línea

Una función normal también puede contener una única sentencia después de los
dos puntos, en la misma línea:

```bg
func identity(value: int32) int32: return value
func notify() void: send_notification()
```

La forma inline conserva el mismo nodo `FUNCTION_BODY` y las mismas reglas de
retorno que la forma indentada. Solo admite una llamada, `return`, `pass` o
`Del`; no admite declaraciones, condicionales, bucles, bloques ASM ni una
segunda sentencia. No existe un `return` implícito para funciones con valor.

Una función `void` puede terminar con una única llamada inline. `pass` no
crea un retorno implícito, por lo que una función `void` que solo use `pass`
debe añadir un `return` en la forma indentada si necesita ser válida.

Los métodos de clase pueden usar la misma forma. Las funciones `@assembler`
mantienen sus reglas actuales y deben usar un cuerpo ASM indentado.

## Condicionales

Una condición debe ser `bool`; `elif` y `else` pertenecen al mismo bloque:

```bg
func sign(value: int32) int32:
    if value < 0:
        return -1
    elif value == 0:
        return 0
    else:
        return 1
```

Las variables creadas dentro del bloque no existen después de él.

## `while`

```bg
func count(limit: int32) int32:
    current: int32 = 0
    while current < limit:
        current += 1
    return current
```

La condición se evalúa antes de cada iteración. `break` sale del bucle más
cercano y `continue` vuelve a evaluar la condición.

## `for ran` y `for in`

`ran` exige iterador unsigned fijo y rango ascendente:

```bg
for i: uint32 ran (0, 4, 1):
    pass
```

`in` recorre la primera dimensión de un array y obtiene su longitud del tipo:

```bg
values: int32[3] = {1, 2, 3}
for i: int32 in values:
    values[i] += 1
```

El iterador es local y de solo lectura. No se puede reutilizar su nombre en un
`for` anidado.

## Retornos especiales

Una función `Never` no vuelve y solo puede terminar mediante una llamada como
sentencia:

```bg
func stop() Never:
    while true:
        pass

func main() int32:
    stop()
```

El compilador considera inalcanzable el código posterior a una llamada
`Never`. Una función normal debe conservar una ruta de retorno para todas sus
rutas alcanzables.
