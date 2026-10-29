# Matriz De Tipos, Palabras Clave Y Metapropiedades

Este documento contiene la especificacion normativa de los tipos nativos, convenciones de constantes, modificadores de bajo nivel y palabras reservadas del compilador **Bagron**.

---

## Matriz De Tipos De Datos

### Enteros Con Signo

| Tipo Bagron | Ancho (Bits) | Descripcion |
| :--- | :---: | :--- |
| `int`, `int32` | 32 | Entero estandar con signo de 32 bits. |
| `int64` | 64 | Entero largo de 64 bits. |
| `int16` | 16 | Entero corto de 16 bits. |
| `int8` | 8 | Entero de 8 bits. |
| `Bint<n>` | `n` | Entero con signo de ancho exacto. |

### Enteros Sin Signo

| Tipo Bagron | Ancho (Bits) | Descripcion |
| :--- | :---: | :--- |
| `uint`, `uint32` | 32 | Entero sin signo de 32 bits. |
| `uint64` | 64 | Entero sin signo de 64 bits. |
| `uint16` | 16 | Entero sin signo de 16 bits. |
| `uint8`, `byte` | 8 | Byte sin signo de 8 bits. |
| `wsize` | 64 | Entero sin signo dependiente de la arquitectura de la maquina. |
| `uBint<n>` | `n` | Entero sin signo de ancho exacto. |

### Punto Flotante

| Tipo Bagron | Ancho (Bits) | Precision |
| :--- | :---: | :--- |
| `middle` | 16 | Media precision IEEE-754. |
| `float` | 32 | Simple precision IEEE-754. |
| `double` | 64 | Doble precision IEEE-754. |

### Caracteres Y Cadenas

| Tipo Bagron | Descripcion |
| :--- | :--- |
| `char` | Caracter individual ASCII. En LLVM ocupa `i8`, pero no es un entero numerico de Bagron. |
| `byte` | Unidad binaria sin signo de 8 bits. Puede inicializarse con un valor numerico o con un byte de cadena. |
| `char[n]` | Buffer ASCII mutable de capacidad fija; la ultima celda se reserva para un `NUL` oculto. |
| `chain` | Cadena estatica, inmutable y de solo lectura. Se emite como bytes UTF-8 terminados en `NUL`; no es un array mutable de `char`. |
| `callptr` | Marcador de puntero callable; su firma se infiere del destino. |
| `bool` | Booleano (`true` o `false`). |
| `void` | Ausencia de valor o tipo de retorno vacio. |

Los punteros se expresan como modificadores `*` sobre el tipo declarado, no como tipos nominales `ptr` o `cptr`.

Los arrays se expresan mediante sufijos `[]` o con una longitud fija entre corchetes:

```bg
edades: int[] = {1, 2, 3}
matriz: int[][] = {{1, 2}, {3, 4}}
nombre: char[10] = "Hola"
bytes: byte[6] = "x0x0xb"
contador: Bint<13> = 10
mask: uBint<5> = 17
```

`char` solo acepta ASCII. En `char[n]`, el tamaño incluye el `NUL` oculto, por
lo que como maximo caben `n - 1` caracteres visibles. El compilador inserta el
terminador al inicializar desde una cadena o un array literal y rellena el
resto con cero. Por ejemplo, `char[] = "Hola"` infiere `char[5]`, mientras
que `char[4] = "Hola"` es invalido. La forma `byte[5] = "x0x0xb"` tambien es
invalida porque ese literal contiene seis bytes.
Los arrays sin tamaño (`[]`) toman su longitud del inicializador.
Por eso una variable sin inicializador no puede usar un tamaño inferido:

```bg
data: int[] = {1, 2, 3}  ; correcto: longitud 3
data: int[]              ; error: no hay datos para inferir la longitud
data: int[3]             ; correcto: tamaño explícito, queda en cero
```

### Modelo De Buffers Deterministas

Bagron adopta un modelo de memoria explicito, cercano a la programacion de
hardware con recursos limitados: cada capacidad, ancho y byte transmitido debe
ser visible en el contrato del programa. El compilador no intenta adivinar una
longitud logica ni insertar asignaciones dinamicas para corregir un buffer.

- Un `char[n]` reserva exactamente `n` celdas, incluida la celda `NUL`.
- Una capacidad insuficiente para un literal produce un error en compilacion.
- Una capacidad mayor conserva sus ceros de relleno; no es una corrupcion,
  pero puede aumentar el trafico cuando se escribe el buffer completo.
- `Len_t` expresa la capacidad de elementos y `Size_t` el tamano total en
  bytes; no representan la cantidad de caracteres visibles.
- En funciones seguras, un parametro array debe declarar su `Len_t`.
- `printa` escribe toda la region descrita por `Size_t`, incluido el relleno,
  sin buscar un `NUL` en runtime.

Este diseño favorece costes predecibles, ausencia de asignaciones ocultas y
control preciso de la ABI. El usuario puede elegir buffers ajustados para
minimizar I/O o buffers sobredimensionados para reservar espacio de trabajo,
pero la eleccion y su coste permanecen explicitos.

`chain` requiere un inicializador y queda constante incluso sin escribir
`const` explícitamente:

```bg
mensaje: chain = "inmutable"
```

La asignacion a `chain` permite una conversion implicita evaluada en
compilacion desde un `char` constante o un `char[n]` constante cuyo contenido
sea conocido. El compilador genera una copia estatica e inmutable sin ejecutar
codigo en runtime. Los valores mutables o dinamicos requieren un tipo de texto
runtime, que aun no forma parte de esta etapa.

La biblioteca `standard.bg` separa la salida de texto estatica de la salida de
buffers mutables: `print(chain)` escribe un `chain`, mientras `printa(char[])`
escribe el buffer completo de caracteres, incluidos sus `NUL` de relleno. Una
funcion puede pedir el tamano automatico de un array con `Len_t`:

```bg
printa(buffer: char[], long: Len_t, size: Size_t) void:
    return
```

El llamador continua escribiendo `printa(buffer)`. El compilador verifica que
`buffer` sea un array con longitud conocida e inserta esa longitud como un
`uint64`/`i64`; no se acepta un escalar, un puntero ni un array de longitud
desconocida. En una funcion segura, todo parametro array debe estar seguido
por su `Len_t` correspondiente; asi la firma declara explicitamente la
capacidad que recibe la funcion. `Len_t` es un parametro especial de funciones
Bagron y no puede usarse en una declaracion `extern` ni como variable local.
`Size_t` funciona igual, pero inserta el tamano en bytes: para arrays
multiplica la longitud por el tamano del elemento y para escalares usa el
tamano del tipo. `printa` usa `Size_t` como cantidad de bytes para `WriteFile`
y no busca un `NUL` antes de terminar el buffer.

La biblioteca estandar incluye `serialize_int`, una funcion tipada que recibe
un array de salida, su `Len_t`, un `int32` y su `Size_t`. La llamada solo
escribe los argumentos visibles; Bagron expande automaticamente los metadatos,
serializa el entero en decimal y conserva el `NUL` final.

Para escribir en una posicion concreta se usa `serialize_int_at`:

```bg
serialize_int_at(buffer, 10, 20)
```

El segundo argumento visible es un indice `uint64` dentro de `buffer`; la
funcion sobrescribe desde esa posicion, comprueba que quepan los digitos y el
`NUL`, y retorna la cantidad de caracteres escritos. Si no hay espacio,
retorna `0` sin modificar el buffer. No inserta ni desplaza datos: una futura
operacion de insercion tendra que ser una funcion distinta.

En la emisión LLVM actual, `char` y `byte` escalares y sus arrays pueden
usarse tanto en globales como en funciones. El acceso por índice se traduce a
`getelementptr`; los tamaños escritos como `[]` se infieren del inicializador.

`Bint<n>` y `uBint<n>` requieren que `n` sea un ancho literal positivo. El
primer tipo admite signo y el segundo no. Pueden combinarse con punteros,
arrays, parametros y retornos.

---

## Modificadores De Puntero Y Constancia

Los punteros se expresan mediante uno o mas modificadores `*` en la declaracion, antes de `:`:

```bg
valor: int
p *: int
pp **: int
```

La constancia del puntero y del valor son independientes:

```bg
p *: int
p *: const int
const p *: int
const p *: const int
valor: const int = 10
```

En estas declaraciones, `;` solo inicia un comentario de linea; no es un
separador ni un terminador de instrucciones.

El `const` antes del identificador solo es valido cuando existe `*`. Para
retornos de funcion, los `*` se escriben despues del tipo:

```bg
func obtener() int*:
func leer() const int*:
```

El operador `$` obtiene una dirección de forma explícita. No se usa `&` para
evitar colisionar con el AND bitwise, que conserva su significado de C:

```bg
valor: int = 10
p *: int = $valor
pp **: int = $p
(p) = 20
resultado: int = ((pp))
```

Cada par de paréntesis elimina un nivel de puntero. La desreferenciación se
comprueba en tiempo de ejecución y una dirección `Null` termina mediante
`llvm.trap`. Para indexar un array se debe tomar la dirección del elemento,
por ejemplo `$datos[0]`; `$datos` por sí solo es ambiguo y se rechaza.

Las funciones son seguras por defecto. Una función segura puede crear un
puntero mediante `$`, recibirlo y reenviarlo, pero solo puede desreferenciar
punteros cuya procedencia sea conocida por el compilador. Esto permite, por
ejemplo, usar `$valor` local o global, pero no leer directamente un puntero
recibido como parámetro ni uno retornado por una función opaca. La asignación a
un puntero es válida; si su procedencia pasa a ser desconocida, la siguiente
desreferenciación exige `@unsafe`.

En una función segura, los índices de arrays deben ser literales o expresiones
constantes que el compilador pueda demostrar dentro del tamaño conocido. Los
índices dinámicos, el indexado de punteros crudos, la aritmética/casts de
punteros y el acceso a memoria de procedencia desconocida requieren una
función `@unsafe`. En un `char[n]`, la escritura sobre la última celda se
rechaza en funciones seguras porque está reservada para el `NUL`. No se
insertan comprobaciones de límites ni de terminador en tiempo de ejecución.

```bg
@unsafe
func leer(pointer *: int) int:
    return (pointer)

@unsafe
func main() int:
    valor: int = 10
    return leer($valor)
```

Una función segura no puede llamar a una función `@unsafe`; una función
`@unsafe` sí puede llamar a una segura. Si `main` llama a una función insegura,
también debe marcarse `@unsafe`. El decorador `@assembler` implica
automáticamente `@unsafe` porque sus plantillas tienen acceso directo a la
ABI y a memoria. Las direcciones de variables locales no pueden escapar
mediante un retorno puntero en funciones seguras; una función insegura asume
esa responsabilidad explícitamente.

Los punteros a funciones se declaran con `callptr` y un nivel `*`:

```bg
func suma(a: int) int:
    return a

const s *: callptr = suma
resultado: int = s(10)
```

La firma del destino se registra durante el analisis semantico. Las llamadas,
miembros e indices pueden encadenarse:

```bg
resultado: int = objeto.metodo(1).campo[0]
resultado: int = suma(otra(5))
```

---

## Constantes En Bagron

La constancia se declara explicitamente con `const` dentro del tipo:

```bg
edad: const int = 10
mensaje: const chain = "inmutable"
```

La forma `const edad: int` es invalida porque el `const` previo al nombre
esta reservado para la constancia del puntero.

---

## Estructuras, Moldes Y Alineacion De Memoria

Estos constructos se registran y validan semánticamente, y sus definiciones se
emiten a LLVM cuando el módulo se compila:

- **`struct`:** Campos ordenados y tipados, sin inicializadores.
- **`mold`:** Tipo nominal distinto de `struct`, con los mismos campos sin inicializadores.
- **`flags`:** Campos enteros escalares con un literal compatible; se emiten como
  una estructura LLVM empaquetada con los anchos declarados.
- **Instancias globales:** Una variable global de cualquiera de estos tipos se
  emite con `zeroinitializer`.
- **`@packed`, `volatile` y `__align__`:** Reservados; producen un diagnóstico de funcionalidad pendiente.

---

## Enumeraciones (`enum`)

Permite definir variantes fuertemente tipadas. La base es `int32` si se omite;
también puede indicarse cualquier tipo entero escalar compatible:

```bg
enum EventType:
    QUIT = 256,
    KEYDOWN = 257,
    KEYUP = 258,

enum SmallEvent int8:
    NONE,
    KEY = 1,
```

Los valores implícitos empiezan en `0`, los explícitos reinician la secuencia y
todos deben caber en el rango del tipo base.

---

## Metapropiedades De Introspeccion Estatica

Las variables exponen metadatos resueltos en tiempo de compilacion mediante sintaxis de propiedad:

| Propiedad | Descripcion |
| :--- | :--- |
| `variable.type` | Retorna una cadena con el nombre estatico del tipo. |
| `variable.size` | Tamaño exacto en bytes de la variable. |
| `variable.len` | Longitud fija declarada en arrays o cadenas. |
| `variable.const` | Indicador binario sobre si el identificador es constante. |
| `variable.visibility` | Indicador de visibilidad (`0` privado, `1` publico). |

---

## Precedencia De Operadores De Expresion (Pratt)

Gram resuelve las expresiones de Bagron segun la siguiente escala de precedencia:

| Precedencia (p) | Operadores | Asociatividad | Categoria |
| :---: | :---: | :---: | :---: |
| **150** | `+`, `-`, `~`, `++`, `--` | Prefijo Unario | Aritmetica / Bit a Bit |
| **80** | `**` | Derecha a Izquierda | Exponenciacion |
| **70** | `*`, `/`, `//`, `%` | Izquierda a Derecha | Multiplicativa |
| **60** | `+`, `-` | Izquierda a Derecha | Aditiva |
| **50** | `<<`, `>>` | Izquierda a Derecha | Desplazamiento de Bits |
| **45** | `&` | Izquierda a Derecha | AND a Nivel de Bits |
| **40** | `^` | Izquierda a Derecha | XOR a Nivel de Bits |
| **35** | `\|` | Izquierda a Derecha | OR a Nivel de Bits |
| **30** | `==`, `!=`, `<`, `<=`, `>`, `>=` | Izquierda a Derecha | Relacional / Igualdad |
| **20** | `&&`, `and` | Izquierda a Derecha | AND Logico |
| **15** | `\|\|`, `or` | Izquierda a Derecha | OR Logico |

---

## Catalogo De Palabras Reservadas

```
# Control De Flujo:
if, elif, else, for, while, ran, return, pass, break, continue

# Declaracion Y Estructura:
func, struct, mold, flags, enum, class, Type, type

# Tipos Escalares Y Memoria:
int, int8, int16, int32, int64, uint, uint8, uint16, uint32, uint64, wsize, byte, float, double, middle, char, bool, void, chain, callptr, Bint, uBint

# Modificadores Y Optimizacion:
public, private, const, inline, packed, __align__

# Modulos Y Enlaces:
clause, import, declare, as

# Literales Del Sistema:
true, false, Null
```
