# Matriz De Tipos, Palabras Clave Y Metapropiedades

Este documento contiene la especificacion normativa de los tipos nativos, convenciones de constantes, modificadores de bajo nivel y palabras reservadas del compilador **Easy-C** (o **c-**).

---

## Matriz De Tipos De Datos

### Enteros Con Signo

| Tipo Easy-C | Equivalente C | Ancho (Bits) | Descripcion |
| :--- | :--- | :---: | :--- |
| `int`, `int32` | `int32_t` | 32 | Entero estandar con signo de 32 bits. |
| `int64` | `int64_t` | 64 | Entero largo de 64 bits. |
| `int16` | `int16_t` | 16 | Entero corto de 16 bits. |
| `int8` | `int8_t` | 8 | Entero de 8 bits. |

### Enteros Sin Signo

| Tipo Easy-C | Equivalente C | Ancho (Bits) | Descripcion |
| :--- | :--- | :---: | :--- |
| `uint`, `uint32` | `uint32_t` | 32 | Entero sin signo de 32 bits. |
| `uint64` | `uint64_t` | 64 | Entero sin signo de 64 bits. |
| `uint16` | `uint16_t` | 16 | Entero sin signo de 16 bits. |
| `uint8`, `byte` | `uint8_t` | 8 | Byte sin signo de 8 bits. |
| `wsize` | `size_t` | 64 | Entero sin signo dependiente de la arquitectura de la maquina. |

### Punto Flotante

| Tipo Easy-C | Equivalente C | Ancho (Bits) | Precision |
| :--- | :--- | :---: | :--- |
| `middle` | `_Float16` | 16 | Media precision IEEE-754. |
| `float` | `float` | 32 | Simple precision IEEE-754. |
| `double` | `double` | 64 | Doble precision IEEE-754. |

### Caracteres, Cadenas Y Punteros

| Tipo Easy-C | Equivalente C | Descripcion |
| :--- | :--- | :--- |
| `char` | `unsigned char` | Caracter individual ASCII / Byte. |
| `chain` | `char*` | Puntero a cadena de caracteres. |
| `bool` | `bool` | Booleano (`true` o `false`, requiere `<stdbool.h>`). |
| `ptr` | `void*` o `T*` | Puntero mutable generico o tipado. |
| `cptr` | `const void*` o `const T*` | Puntero constante de solo lectura. |
| `void` | `void` | Ausencia de valor o tipo de retorno vacio. |

---

## Semantica Estricta De Punteros

Easy-C implementa control riguroso de calificaciones de puntero:
- La asignacion `ptr -> cptr` es valida (promocion segura a solo lectura).
- La asignacion `cptr -> ptr` genera error estatico de compilacion para prevenir la perdida del calificador `const`.
- El literal `Null` solo puede asignarse a identificadores definidos con `ptr` o `cptr`.

---

## Convencion De Constantes En c-

Easy-C **no** utiliza la palabra reservada `const`. La inmutabilidad se rige estrictamente por la nomenclatura del identificador:

- **Todo identificador escrito en MAYUSCULAS es una constante en tiempo de compilacion:**
  ```egl
  BUFFER_SIZE: uint32 = 4096
  VELOCIDAD_LUZ: float = 299792458.0
  ```
- En el backend C se emite con calificador `const`.
- Si el codigo intenta reasignar un valor a un identificador en mayusculas, el validador semantico emite un error fatal inmediato.

---

## Estructuras, Moldes Y Alineacion De Memoria

c- proporciona herramientas directas para interactuar con hardware y APIs de C sin desajustes de memoria:

- **Estructuras planas (`struct`):** Layout binario identico a structs de C.
- **Moldes (`mold`):** Tipos semanticos reutilizables para plantillas de datos.
- **Modificador `__packed__`:** Elimina el padding de alineacion interna, traduciendose a `__attribute__((packed))` o `#pragma pack(push, 1)`.
- **Modificador `__align__ N`:** Fuerza alineacion de hardware a limites de N bytes (`__attribute__((aligned(N)))`).
- **Campos a nivel de bits (`flags`):** Permite declarar bitfields directos (`tipo [nombre] : bits;`) para protocolos binarios y registros de microcontroladores.

---

## Enumeraciones (`enum`)

Permite definir variantes fuertemente tipadas compiladas a bloques `typedef enum` en C:

```egl
enum EventType:
    QUIT = 256
    KEYDOWN = 257
    KEYUP = 258
```

El compilador antepone el nombre del enum a cada variante en C para blindar el espacio global contra colisiones de simbolos.

---

## Metapropiedades De Introspeccion Estatica

Las variables exponen metadatos resueltos en tiempo de compilacion mediante sintaxis de propiedad:

| Propiedad | Emision en C | Descripcion |
| :--- | :--- | :--- |
| `variable.type` | `"tipo"` | Retorna una cadena con el nombre estatico del tipo. |
| `variable.ptr` | `&variable` | Obtiene la direccion de memoria de la variable como puntero. |
| `variable.size` | `sizeof(...)` | Emite el tamano exacto en bytes de la variable. |
| `variable.len` | `N` | Longitud fija declarada en arrays o cadenas. |
| `variable.const` | `1` o `0` | Indicador binario sobre si el identificador es constante. |
| `variable.visibility` | `1` o `0` | Indicador de visibilidad (`0` privado, `1` publico). |

---

## Precedencia De Operadores De Expresion (Pratt)

Gram resuelve las expresiones de Easy-C segun la siguiente escala de precedencia:

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
if, elif, else, for, while, ran, in, return, pass, break, continue

# Declaracion Y Estructura:
struct, mold, flags, enum, class, Type, type

# Tipos Escalares Y Memoria:
int, int8, int16, int32, int64, uint, uint8, uint16, uint32, uint64, wsize, byte, float, double, middle, char, bool, ptr, cptr, void, chain

# Modificadores Y Optimizacion:
public, private, __inline__, __packed__, __align__

# Modulos Y Enlaces:
clause, include, import, declare, as

# Literales Del Sistema:
true, false, Null
```
