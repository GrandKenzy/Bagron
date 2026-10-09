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
| `type` | N/A | Metatipo | Representa un identificador de tipo como parametro o valor. |

---

## Tipos Genericos y Contenedores

Easy-C soporta la instanciacion de contenedores de tamaño fijo mediante la notacion de corchetes:

* `array[T, N]`: Define un arreglo unidimensional contiguo de `N` elementos de tipo `T`.
  * Ejemplo: `array[int, 10] numeros` produce `int64_t numeros[10];`.
* `chain[N]`: Define una cadena de longitud fija `N`.
  * Ejemplo: `chain[64] buffer` produce `char buffer[64];`.
* `ptr T` o `__void_p_t__ T`: Define un puntero especifico a un tipo base `T`.
  * Ejemplo: `ptr int cursor` produce `int64_t* cursor;`.

---

## Metapropiedades Magicas de Expresiones

El lenguaje expone propiedades de introspeccion estatica accesibles sobre identificadores de variable:

| Propiedad | Retorno en C | Descripcion |
| :--- | :--- | :--- |
| `variable.type` | `"tipo"` | Retorna una cadena literal con la declaracion del tipo (ej. `"int"` o `"array[int, 5]"`). |
| `variable.ptr` | `&variable` | Obtiene la direccion de memoria de la variable como puntero. |
| `variable.size` | `sizeof(...)` | Emite el tamaño en bytes ocupado por la variable o estructura. |
| `variable.len` | `N` | Longitud fija declarada en arrays o cadenas `chain`. |
| `variable.__const__`, `.const` | `1` o `0` | Indicador binario en tiempo de compilacion sobre si la variable es constante. |
| `variable.__visibility__`, `.visibility`| `1` o `0` | Indicador binario: `0` si es privada; `1` si es publica. |
| `variable.value` | **Error** | Prohibido. Lanza un fallo en compilacion para proteger encapsulamiento interno. |

---

## Catalogo de Palabras Reservadas

```
# Control de Flujo:
if, else, for, return

# Declaracion y Estructura:
struct, class, type, object, int, uint, float, double, middle, char, bool, str, ptr, void

# Modificadores de Visibilidad y Optimizacion:
public, private, __inline__

# Modulos e Integracion:
clause, include, import, as

# Literales del Sistema:
true, false, Null
```
