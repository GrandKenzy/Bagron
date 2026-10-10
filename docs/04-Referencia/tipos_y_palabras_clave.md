# Matriz de Tipos, Palabras Clave y Metapropiedades

Este documento contiene la especificacion normativa de los tipos nativos, palabras reservadas, modificadores y propiedades magicas reconocidas por el compilador de Easy-C (EGL).

---

## Matriz de Tipos de Datos

### 1. Tipos Enteros con Signo

| Tipo EGL | Alias Interno | Equivalente C | Ancho (Bits) | Rango Aprox. / Descripcion |
| :--- | :--- | :--- | :--- | :--- |
| `int`, `int64` | `__int_t__`, `__int64_t__` | `int64_t` | 64 bits | -9.22e18 a 9.22e18 (Entero estandar por defecto). |
| `int32` | `__int32_t__` | `int32_t` | 32 bits | -2,147,483,648 a 2,147,483,647. |
| `int16` | `__int16_t__` | `int16_t` | 16 bits | -32,768 a 32,767. |
| `int8` | `__int8_t__` | `int8_t` | 8 bits | -128 a 127. |

### 2. Tipos Enteros sin Signo

| Tipo EGL | Alias Interno | Equivalente C | Ancho (Bits) | Rango Aprox. / Descripcion |
| :--- | :--- | :--- | :--- | :--- |
| `uint`, `uint64` | `__uint_t__`, `__uint64_t__` | `uint64_t` | 64 bits | 0 a 18.44e18. |
| `uint32` | `__uint32_t__` | `uint32_t` | 32 bits | 0 a 4,294,967,295. |
| `uint16` | `__uint16_t__` | `uint16_t` | 16 bits | 0 a 65,535. |
| `uint8` | `__uint8_t__` | `uint8_t` | 8 bits | 0 a 255 (Byte sin signo). |

### 3. Tipos en Punto Flotante

| Tipo EGL | Alias Interno | Equivalente C | Ancho (Bits) | Precision y Estandar |
| :--- | :--- | :--- | :--- | :--- |
| `middle` | `__middle_t__` | `_Float16` | 16 bits | Media precision IEEE 754 (con promocion a double en printf). |
| `float` | `__float_t__` | `float` | 32 bits | Simple precision IEEE 754. |
| `double` | `__double_t__` | `double` | 64 bits | Doble precision IEEE 754. |

### 4. Texto, Caracteres y Punteros

| Tipo EGL | Alias Interno | Equivalente C | Descripcion |
| :--- | :--- | :--- | :--- |
| `char` | `__char_t__` | `char` | Caracter individual ASCII / Byte. |
| `str`, `string` | N/A | `char*` | Puntero a cadena inmutable terminada en nulo (`\0`). |
| `chain[N]` | N/A | `char[N]` | Buffer contiguo de caracteres de dimension estatica `N`. |
| `ptr`, `pointer` | `__void_p_t__` | `void*` | Puntero opaco generico a memoria. |
| `void` | N/A | `void` | Ausencia de valor o tipo de retorno vacio. |
| `bool`, `boolean` | N/A | `bool` | Booleano (`true` o `false`, requiere `<stdbool.h>`). |
| `type` | `__type_t__` | Metatipo | Representa un identificador de tipo como parametro o valor. |
| `any` | N/A | `void*` | Tipo comodin generico. Se utiliza para representar valores o punteros sin restriccion de tipo estricta, mapeandose a `void*` en C. |

---

## Tipos Genericos y Contenedores

Easy-C soporta la instanciacion de contenedores de tamaño fijo y tipos genericos:

* `array[T, N]`: Define un arreglo unidimensional contiguo de `N` elementos de tipo `T`.
  * Ejemplo: `array[int, 10] numeros` produce `int64_t numeros[10];`.
* `chain[N]`: Define una cadena de longitud fija `N`.
  * Ejemplo: `chain[64] buffer` produce `char buffer[64];`.
* `ptr T` o `__void_p_t__ T`: Define un puntero especifico a un tipo base `T`.
  * Ejemplo: `__void_p_t__ FRect rect` produce `FRect* rect;`.
  * Ejemplo: `__void_p_t__ char cursor` produce `char* cursor;`.

### Intrinsic `__arrof__`

El intrinsic `__arrof__` es el mecanismo primitivo interno sobre el que se implementa la construccion de arreglos estaticos (`array[T, N]`). Permite parametrizar el tipo de elemento (`T`) y la dimension estatica (`N`), siendo resuelto en tiempo de compilacion por el sistema de tipos (`resolve_generic_type`) para emitir la dimension y el tipo en C (`T nombre[N];`).

### Simbolo `__fronted__`

El identificador magico `__fronted__` es un meta-simbolo interno del compilador utilizado en definiciones de tipos primitivos (como `pstring` y cadenas nativas) para apuntar directamente a la direccion frontal del buffer subyacente en tiempo de compilacion, emitiendo una referencia vacia/frontal directa sin sobrecosto de abstraccion.

### Operador `sizeof(...)`

Easy-C provee la funcion intrinseca `sizeof(T)` o `sizeof(variable)` que se traduce directamente al operador nativo `sizeof(...)` en C, complementando el acceso mediante la propiedad `variable.size`.

---

## Constantes en Easy-C (Norma de Identificadores)

> [!IMPORTANT]
> **Easy-C NO utiliza la palabra reservada `const`.**
> La inmutabilidad se define de forma estricta mediante la nomenclatura del identificador:
> **Todo identificador escrito en MAYUSCULAS es una constante inmutable.**
>
> * Ejemplo: `uint32 EVENT_QUIT = 256` o `float VELOCIDAD_LUZ = 299792458.0`.
> * En C, el compilador emite el calificador nativo `const` (ej. `const uint32_t EVENT_QUIT = 256;`).
> * Si el codigo intenta reasignar una constante (`EVENT_QUIT = 0`), el compilador detiene el proceso con un error estatico en tiempo de compilacion.

---

## Enumeraciones (`enum`)

Easy-C soporta la definicion ergonomica de enumeraciones que se compilan a `typedef enum` nativos en C:

### 1. Sintaxis Soportadas

* **Multilínea con valores explícitos:**
  ```egl
  enum EventType:
      QUIT = 256
      KEY_DOWN = 257
  ```

* **Multilínea secuencial automática:**
  ```egl
  enum Color:
      RED
      GREEN
      BLUE
  ```

* **Línea única separada por comas:**
  ```egl
  enum Direction: NORTH, SOUTH, EAST, WEST
  ```

* **Sintaxis de llaves:**
  ```egl
  enum Mode {
      READ = 1,
      WRITE = 2
  }
  ```

### 2. Uso y Resolución de Miembros

Los miembros del enum pueden accederse con el espacio de nombres del enum o directamente si están en el ámbito:
```egl
Color c = Color.RED
if event.type == EventType.QUIT:
    running = false
```

Al importar desde módulos, se puede usar `declare <modulo>.<Enum> as <Enum>` para resolver miembros calificados sin colisiones de nombres en C.

---

## Metapropiedades Magicas de Expresiones

El lenguaje expone propiedades de introspeccion estatica accesibles sobre identificadores de variable:

| Propiedad | Retorno en C | Descripcion |
| :--- | :--- | :--- |
| `variable.type` | `"tipo"` | Retorna una cadena literal con la declaracion del tipo (ej. `"int"` o `"array[int, 5]"`). |
| `variable.ptr` | `&variable` | Obtiene la direccion de memoria de la variable como puntero. |
| `variable.size` | `sizeof(...)` | Emite el tamaño en bytes ocupado por la variable o estructura. |
| `variable.len` | `N` | Longitud fija declarada en arrays o cadenas `chain`. |
| `variable.const` | `1` o `0` | Indicador binario en tiempo de compilacion sobre si la variable es constante. |
| `variable.visibility` | `1` o `0` | Indicador binario: `0` si es privada; `1` si es publica. |
| `variable.value` | **Error** | Prohibido. Lanza un fallo en compilacion para proteger encapsulamiento interno. |

---

## Catalogo de Palabras Reservadas

```
# Control de Flujo:
if, elif, else, for, while, ran, in, return, pass

# Declaracion y Estructura:
enum, struct, class, Type, type

# Tipos Intrínsecos Primitivos (Backend):
__int_t__, __int8_t__, __int16_t__, __int32_t__, __int64_t__, __uint_t__, __uint8_t__, __uint16_t__, __uint32_t__, __uint64_t__, __float_t__, __middle_t__, __double_t__, __char_t__, __bool_t__, __void_t__, __void_p_t__, __type_t__, __arrof__, __size_t__

# Tipos Definidos en standard.egl:
int, int8, int16, int32, int64, uint, uint8, uint16, uint32, uint64, float, double, middle, char, bool, ptr, pointer, void, any, array, chain, pstring

# Modificadores de Visibilidad y Optimizacion:
public, private, __inline__

# Modulos e Integracion:
clause, include, import, load, declare, as

# Operadores e Intrinsics:
sizeof

# Literales del Sistema:
true, false, Null
```
