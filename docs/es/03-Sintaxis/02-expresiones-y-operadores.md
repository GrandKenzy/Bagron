# Expresiones y operadores

## Operaciones numéricas

Bagron mantiene el tipo y el signo explícitos. Los enteros de la misma familia
pueden ensancharse de forma segura, pero no se mezclan signed y unsigned:

```bg
a: int8 = 1
b: int16 = 2
total: int16 = a + b

mask: uint8 = 3
shifted: uint16 = mask << 2
```

Los operadores aritméticos y bitwise exigen operandos compatibles. No existe un
cast general que oculte truncamientos.

## Comparaciones y lógica

Las comparaciones producen `bool`. Las condiciones no convierten enteros o
punteros automáticamente:

```bg
ready: bool = true
blocked: bool = false

if ready && not blocked:
    pass

if ready || blocked:
    pass
```

`&&` y `||` son los operadores binarios lógicos; `not` es la negación. `and` y
`or` no son palabras válidas.

## Lvalues, miembros y llamadas

Una asignación necesita almacenamiento modificable. Los campos y elementos se
leen o escriben con la misma forma:

```bg
struct Pair:
    left: int32
    right: int32

func main() int32:
    pair: Pair
    pair.left = 2
    pair.right += 3
    return pair.left + pair.right
```

Una llamada `void` es una sentencia, no un valor. Los métodos de instancia
usan `object.method()`; los métodos `@static`, `Type.method()`.

## Texto

`char[]` es un array mutable de caracteres; `chain` es texto constante en
rodata. Un `chain` con longitud conocida puede inicializar un `char[]`, pero la
conversión inversa no existe:

```bg
text: chain = "Hola"
copy: char[] = text
copy[0] = "h"
```
