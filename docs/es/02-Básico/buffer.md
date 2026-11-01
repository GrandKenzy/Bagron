# `buffer`

`buffer` representa un bloque de memoria dinámica cruda compuesto por bytes.
Su tamaño es exacto y forma parte de la declaración. Un `buffer` no crece ni
cambia de capacidad después de ser creado.

`buffer` no es un alias de `byte[N]`:

- `byte[N]` es un array ordinario con almacenamiento estático según el
  contexto donde se declare;
- `buffer[N]` solicita una reserva de memoria dinámica de exactamente `N`
  bytes.

No existe conversión implícita entre ambos tipos.

## Creación

El tamaño debe ser una expresión entera resoluble en compilación y debe ser
mayor que cero:

```bg
datos: buffer[8 * 100] = 0
```

La reserva contiene exactamente `800` bytes. El inicializador escalar `0`
rellena toda la reserva con cero; no crea un solo elemento de tamaño `800`.

El tamaño no puede ser cero ni negativo:

```bg
empty: buffer[0]       ; error
negative: buffer[-4]   ; error
```

La memoria se solicita en tiempo de ejecución, pero su capacidad queda
determinada por el tipo durante la compilación.

## Escritura y lectura

Un `buffer[N]` puede indexarse como una secuencia de `byte`:

```bg
datos: buffer[4] = 0
datos[0] = 65
datos[1] = 66
value: byte = datos[0]
```

El índice debe referirse a una posición entre `0` y `N - 1`. En código seguro,
un índice cuyo valor solo se conozca en tiempo de ejecución debe comprobarse
contra la capacidad del buffer. Un acceso fuera de rango produce un error de
ejecución; no se convierte silenciosamente en aritmética de punteros.

El contenido de un `buffer` es mutable y se interpreta como datos crudos. El
tipo no añade terminación `NUL`, semántica de texto ni conversión automática a
`char[]` o `chain`.

## Tamaño inferido

Los corchetes vacíos pueden usarse cuando el inicializador permite calcular la
capacidad completa:

```bg
buffer1: buffer[3] = {1, 2, 3}
buffer2: buffer[2] = {4, 5}
gigante: buffer[] = buffer1 + buffer2
```

En este caso, `gigante` se resuelve como `buffer[5]`.

`buffer[]` en una declaración con inicializador no significa un buffer de
tamaño desconocido ni uno que pueda crecer. Significa que el compilador debe
inferir la capacidad a partir del valor inicial.

## Concatenación

La suma de dos buffers crea una nueva reserva y copia sus contenidos en orden:

```bg
left: buffer[2] = {10, 20}
right: buffer[3] = {30, 40, 50}
all: buffer[] = left + right ; buffer[5]
```

La capacidad resultante es la suma de las capacidades de los operandos:

```text
buffer[N1] + buffer[N2] = buffer[N1 + N2]
```

Los operandos originales no se modifican. La operación no amplía ninguno de
ellos y puede fallar si no es posible obtener la nueva reserva.

## Liberación

`Del` reconoce el tipo `buffer` y libera el bloque dinámico que posee la
variable:

```bg
datos: buffer[8 * 100] = 0
Del datos
```

Después de liberar, el descriptor de `datos` queda en cero. `Del` no es un
método y no añade atributos implícitos al tipo.

El compilador mantiene un estado estático para cada buffer durante el análisis:

- `owned`: la variable posee el bloque y puede ejecutar `Del` una vez;
- `borrowed`: la variable es un parámetro prestado, puede leerse y modificarse,
  pero no puede liberarse;
- `dead`: el bloque ya fue liberado y cualquier lectura, escritura, llamada o
  segundo `Del` se diagnostica como error.

Estos estados no forman parte del descriptor, no agregan comprobaciones al
programa generado y no cambian la ABI: son una comprobación de tiempo de
compilación de coste cero en ejecución.

## Parámetros de función

Un `buffer` puede recibirse como préstamo y debe declarar `Len_t`:

```bg
func consume(data: buffer[], length: Len_t) usize:
    return length
```

`Len_t` contiene la longitud actual en bytes del descriptor. `Size_t` no se
admite para `buffer`, porque todos sus elementos tienen tamaño `1`.

`buffer[N]` exige un buffer con esa capacidad exacta; `buffer[]` acepta
cualquier capacidad conocida en tiempo de ejecución. El parámetro conserva el
descriptor por valor, pero la memoria sigue perteneciendo al llamador: la
función receptora no puede ejecutar `Del` sobre él.

También puede declararse un préstamo exclusivo:

```bg
func consume(data: unique buffer[], length: Len_t, region: Region_t) usize:
    return length
```

`Region_t` es inmutable, oculto en la llamada y solo se acepta cuando el
compilador demuestra una procedencia de almacenamiento concreta. La función
no puede recibir dos argumentos que representen la misma región `unique`.
Los buffers mantienen su descriptor por valor; por eso esta comprobación no
cambia todavía la ABI ni añade `noalias` al descriptor.

No se permite copiar ni retornar buffers. Una función puede recibir un buffer
como préstamo, modificarlo y devolver únicamente datos intrínsecos u objetos
por valor; el buffer siempre permanece bajo responsabilidad del llamador.

## Alcance actual

Este documento fija la representación, creación, indexación, inicialización,
concatenación, liberación y expansión `Len_t` de `buffer`. La transferencia de
propiedad y el retorno desde funciones quedan fuera del modelo del lenguaje.
La liberación automática al salir de un ámbito continúa pendiente; por ahora la
liberación es explícita mediante `Del`. En esta fase el análisis de flujo es
conservador: si alguna rama o iteración puede dejar un buffer en `dead`, no se
permite usarlo después de ese punto. Por la misma razón, `Del` dentro de un
bucle se rechaza: una segunda iteración no podría volver a liberar el mismo
binding `owned`.
