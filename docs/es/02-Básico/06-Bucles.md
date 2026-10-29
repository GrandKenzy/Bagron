# Bucles

`for` es el bucle numérico por rango de Bagron. Repite un bloque mientras un
iterador unsigned avance desde un inicio hasta un límite exclusivo.

No es un `foreach`: no recibe arrays, matrices, `chain` ni otros objetos
iterables. El rango siempre está escrito explícitamente y el compilador conoce
el tipo del iterador desde la firma del bucle.

## Sintaxis

La forma canónica es:

```bg
for nombre: uint32 ran (inicio, limite, paso):
    ; cuerpo
```

Los tres valores del rango son obligatorios:

| Parte | Significado |
|:---|:---|
| `nombre` | Iterador local, visible únicamente dentro del cuerpo. |
| Tipo | Uno de `uint8`, `uint16`, `uint32` o `uint64`. |
| `inicio` | Primer valor posible del iterador. Es inclusivo. |
| `limite` | Frontera superior. Es exclusiva. |
| `paso` | Incremento aplicado después de cada iteración. Debe ser mayor que cero. |

Ejemplo:

```bg
func count() int32:
    total: int32 = 0

    for i: uint32 ran (0, 4, 1):
        total += 1

    return total
```

El cuerpo se ejecuta cuatro veces, con `i` igual a `0`, `1`, `2` y `3`.
El `4` nunca se procesa porque el límite final no forma parte del rango.

## Tipos permitidos

El iterador solo puede usar un entero unsigned de ancho fijo:

```text
uint8
uint16
uint32
uint64
```

Cuando se escribe `uint*` en esta documentación, el asterisco es un comodín
para la familia `uint8`–`uint64`; no representa un puntero de Bagron.

No existen los tipos genéricos `int` ni `uint`. Tampoco se permite usar como
iterador:

- `int8`, `int16`, `int32` o `int64`;
- `usize` o `isize`;
- `byte` o `char`;
- `bool`;
- `Bint<n>` o `uBint<n>`;
- punteros, arrays, matrices, `chain`, `Len_t` o `Size_t`.

Estos errores son independientes de `@unsafe`: una función insegura tampoco
puede cambiar el tipo requerido por el `for`.

```bg
for a: uint32 ran (0, 4, 1):
    pass                         ; válido

for b: int32 ran (0, 4, 1):
    pass                         ; error: el iterador no es unsigned fijo

for c: uint ran (0, 4, 1):
    pass                         ; error: uint no existe
```

## Compatibilidad del rango

`inicio`, `limite` y `paso` deben ser compatibles con el tipo del iterador.
Se conserva la regla general de Bagron:

- no se cambia el signo;
- no se permite estrechar el ancho;
- un valor de un unsigned más pequeño puede escalar hacia el unsigned del
  iterador si el cambio es seguro;
- un entero signed no se convierte automáticamente en unsigned;
- un literal solo es válido si cabe en el tipo esperado.

```bg
small: uint8 = 1

for i: uint32 ran (small, 10, 1):
    pass                             ; válido: uint8 -> uint32

wide: uint64 = 1

for j: uint32 ran (wide, 10, 1):
    pass                             ; error: uint64 -> uint32

signed_value: int32 = 1

for k: uint32 ran (signed_value, 10, 1):
    pass                             ; error: no se cambia el signo
```

Los literales positivos usuales pueden usarse porque el compilador verifica
que su valor quepa en el tipo del rango. Un paso negativo no es compatible con
un iterador unsigned:

```bg
for i: uint32 ran (3, 0, -1):
    pass                             ; error
```

No existen rangos descendentes en el `for` actual. Si se necesita recorrer en
sentido inverso, debe expresarse mediante otra lógica explícita y un tipo
adecuado fuera de este bucle.

## Límite dependiente del target

Aunque el iterador sea `uint8`, `uint16`, `uint32` o `uint64`, el rango máximo
que puede recorrer un `for` depende del target seleccionado. Durante la
compilación, Bagron calcula el límite usando el máximo representable por un
entero signed del ancho del target:

| Target | Límite interno del rango |
|:---|---:|
| 32 bits | `2 147 483 647` |
| 64 bits | `9 223 372 036 854 775 807` |

Ese límite es una regla interna del compilador. No es un tipo, un identificador
ni un metatipo que el usuario pueda escribir.

El límite se aplica a `inicio`, `limite`, `paso` y a cualquier valor que el
bucle deba usar. Con un literal, la comprobación ocurre en compilación:

```bg
clause Arch 'x86'

func bad() int32:
    for i: uint64 ran (0, 2147483648, 1):
        pass                         ; error: supera el límite del target
    return 0
```

Si el valor es dinámico, el compilador genera una validación antes de entrar
al bucle. Un valor fuera del límite produce una trampa controlada; nunca se
inicia un rango que el target no pueda representar de forma segura.

Como el límite final es exclusivo, usar exactamente el límite como `limite`
permite producir valores hasta `limite - 1`:

```text
for i: uint64 ran (0, limite, 1)
```

El propio `limite` no forma parte de la iteración.

## `step` y casos límite

El paso debe ser distinto de cero. Si el compilador conoce que es cero, lo
rechaza directamente:

```bg
for i: uint32 ran (0, 10, 0):
    pass                             ; error en compilación
```

Si proviene de una variable o una expresión dinámica, se comprueba antes de
entrar al bucle. Un cero dinámico produce una trampa segura y no un bucle
infinito.

Los casos de frontera se comportan así:

| Rango | Resultado |
|:---|:---|
| `inicio == limite` | El cuerpo no se ejecuta. |
| `inicio > limite` | El cuerpo no se ejecuta. No hay descenso implícito. |
| `paso > limite` | Puede ejecutarse una vez si `inicio < limite`. |
| `paso == 0` | Error de compilación o trampa dinámica. |
| Valor sobre el límite del target | Error de compilación o trampa dinámica. |
| Siguiente valor igual o mayor que `limite` | El bucle termina sin materializar un valor fuera del rango. |

El incremento no se deja envolver silenciosamente. Esto permite que un rango
cercano al máximo del tipo unsigned termine correctamente sin regresar a cero.

## Alcance del iterador

El iterador pertenece al `for` y solo está disponible en su cuerpo:

```bg
func bad() int32:
    for i: uint32 ran (0, 3, 1):
        pass

    return i                         ; error: i ya no existe
```

El iterador también es de solo lectura. El compilador controla su incremento y
el cuerpo no puede modificarlo:

```bg
func bad() int32:
    for i: uint32 ran (0, 3, 1):
        i = 2                         ; error

    return 0
```

Un nombre puede reutilizarse después de que termine su `for`, porque el
iterador anterior ya no está activo. Durante un anidamiento, en cambio, el
nombre debe estar libre.

## Bucles anidados

Los bucles anidados deben usar iteradores distintos:

```bg
func nested() int32:
    total: int32 = 0

    for outer: uint32 ran (0, 2, 1):
        for inner: uint32 ran (0, 3, 1):
            total += 1

    return total
```

Repetir el iterador activo es un error de alcance:

```bg
func bad() int32:
    for i: uint32 ran (0, 2, 1):
        for i: uint32 ran (0, 2, 1):
            pass                         ; error: i ya está ocupado

    return 0
```

El error se produce aunque ambos bucles usen el mismo tipo y el mismo rango.
El nombre debe ser inequívoco mientras exista el bucle exterior.

## `break`

`break` abandona inmediatamente el bucle más cercano. No ejecuta el paso ni
vuelve a evaluar su condición:

```bg
func first() int32:
    count: int32 = 0

    for i: uint32 ran (0, 10, 1):
        if i == 3:
            break
        count += 1

    return count                         ; 3
```

En bucles anidados, `break` solo abandona el nivel donde aparece. Para salir
de varios niveles se necesita una decisión explícita en cada nivel.

## `continue`

`continue` omite el resto del cuerpo actual, ejecuta el incremento del `for` y
regresa a la condición:

```bg
func skip_one() int32:
    count: int32 = 0

    for i: uint32 ran (0, 5, 1):
        if i == 2:
            continue
        count += 1

    return count                         ; 4
```

Si el cuerpo contiene un `while` o un `for` interno, `continue` afecta al
bucle más cercano.

## Arrays y matrices

`for` no convierte automáticamente un array en un iterador ni modifica las
reglas de arrays estáticos. Un índice calculado con el iterador sigue estando
sujeto a la comprobación de límites:

```bg
@unsafe
func sum(values: int32[3]) int32:
    total: int32 = 0
    for i: uint32 ran (0, 3, 1):
        total += values[i]
    return total
```

La forma `@unsafe` del ejemplo solo autoriza el índice dinámico; no permite
usar un tipo de iterador inválido, repetir nombres activos ni superar el
límite máximo del target. Las dimensiones de una matriz continúan siendo
parte del tipo y no se pierden dentro del bucle.

## `while`

`while` repite un bloque mientras una condición sea verdadera. A diferencia de
`if`, su condición no admite conversión implícita desde enteros: debe tener
tipo `bool`. Las comparaciones y las expresiones lógicas producen `bool` y son
formas normales de construir la condición.

```bg
func count_until(limit: int32) int32:
    count: int32 = 0

    while count < limit:
        count += 1

    return count
```

También se pueden usar directamente los literales booleanos cuando el cuerpo
contiene una salida explícita:

```bg
while true:
    if ready:
        break

while false:
    pass                         ; no se ejecuta ninguna vez
```

La condición se evalúa antes de cada iteración, incluso después de un
`continue`. Por eso un `while false` no entra al cuerpo y un `while true` solo
termina si el cuerpo cambia la condición, ejecuta `break` o abandona la
función con `return`.

El cuerpo de un `while` no satisface por sí mismo el retorno obligatorio de una
función: el bucle puede no ejecutarse. Una función con retorno debe conservar
una ruta de `return` después del bucle o en una estructura condicional que
cubra todas sus ramas.

Estas formas son errores:

```bg
while 1:                         ; error: el entero no es bool
    pass

value: int32 = 1
while value:                     ; error: no hay verdad implícita para enteros
    pass
```

`@unsafe` no relaja esta regla. La seguridad del `while` depende de una
condición booleana explícita, no del nivel de seguridad de la función.

`break` y `continue` siempre afectan al bucle más cercano. En un `while`,
`break` salta al final del bucle y `continue` vuelve a evaluar la condición;
no existe un incremento oculto como en `for`.

```bg
func nested() int32:
    total: int32 = 0
    outer: bool = true

    while outer:
        inner: bool = true
        while inner:
            total += 1
            inner = false
        outer = false

    return total
```

La condición puede depender de variables mutables, pero su tipo sigue siendo
estático. Un valor `int32`, `uint32`, `byte`, un puntero, un array o una matriz
no puede usarse directamente como condición de `while`.

## Operadores lógicos

Bagron usa símbolos para las operaciones lógicas binarias:

| Operador | Significado |
|---|---|
| `&&` | conjunción lógica; ambos operandos deben ser `bool`. |
| `||` | disyunción lógica; ambos operandos deben ser `bool`. |
| `not` | negación lógica unaria; su operando debe ser `bool`. |

`and` y `or` no son palabras del lenguaje. Escribirlas como operadores produce
un error de sintaxis; deben escribirse siempre como `&&` y `||`.

```bg
ready: bool = true
blocked: bool = false

if ready && not blocked:
    pass

if ready || blocked:
    pass
```

No existe conversión implícita de enteros, punteros o arrays a `bool`. La
restricción también se aplica dentro de `&&`, `||` y `not`, incluso en una
función marcada como `@unsafe`.

## Alcance de las variables en bloques

Los cuerpos de `if`, `elif`, `else`, `while` y `for` tienen alcance léxico.
Declarar una variable dentro de uno de ellos es válido y no crea memoria
dinámica: el compilador reserva su almacenamiento estático al entrar a la
función.

- Un escalar local debe incluir su inicializador en la declaración.
- Los arrays de tamaño fijo y los agregados reciben almacenamiento estático
  determinista y pueden poblarse después elemento por elemento.
- Una variable del bloque solo puede usarse dentro de ese bloque y sus bloques
  hijos.
- No se permite ocultar ni reutilizar el nombre de una variable local en otra
  declaración de la misma función.
- El iterador de `for` sigue siendo una excepción controlada: solo vive durante
  ese bucle, es de solo lectura y puede volver a usarse cuando el `for` termina.

```bg
func example(enabled: bool) int32:
    result: int32 = 0
    if enabled:
        contribution: int32 = 7
        result = contribution
    return result
```

`contribution` no existe después del `if`; `result` sí, porque fue declarado
en el alcance exterior de la función.

## Resumen

Las reglas del `for` son:

- el iterador pertenece a la familia unsigned fija: `uint8`, `uint16`, `uint32` o `uint64`;
- `int` y `uint` genéricos no existen;
- el rango es ascendente y su límite final es exclusivo;
- el paso debe ser positivo y distinto de cero;
- el máximo del rango se calcula durante la compilación según el target;
- los valores dinámicos se validan antes de iniciar el bucle;
- el iterador es local, de solo lectura y no puede repetirse en un anidamiento;
- `break` sale del bucle más cercano;
- `continue` ejecuta el paso y continúa con la siguiente condición;
- no hay conversiones silenciosas, descenso implícito ni envolvimiento inseguro.

Para `while`, además:

- la condición debe ser un `bool` escalar;
- se evalúa antes de cada iteración;
- `break` sale sin reevaluar otra vez la condición;
- `continue` vuelve directamente a la evaluación de la condición;
- `@unsafe` no permite usar enteros como booleanos.
