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
| `char` | Caracter individual ASCII / Byte. |
| `chain` | Cadena de caracteres. |
| `callptr` | Marcador de puntero callable; su firma se infiere del destino. |
| `bool` | Booleano (`true` o `false`). |
| `void` | Ausencia de valor o tipo de retorno vacio. |

Los punteros se expresan como modificadores `*` sobre el tipo declarado, no como tipos nominales `ptr` o `cptr`.

Los arrays se expresan mediante sufijos `[]`:

```bg
edades: int[] = [1, 2, 3]
matriz: int[][] = [[1, 2], [3, 4]]
contador: Bint<13> = 10
mask: uBint<5> = 17
```

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

En la fase actual, estos constructos se registran y validan semánticamente,
pero todavía no tienen layout físico ni instancias LLVM:

- **`struct`:** Campos ordenados y tipados, sin inicializadores.
- **`mold`:** Tipo nominal distinto de `struct`, con los mismos campos sin inicializadores.
- **`flags`:** Campos enteros escalares con un literal compatible conservado como metadata.
- **`@packed`, `volatile` y `__align__`:** Reservados; producen un diagnóstico de funcionalidad pendiente.

---

## Enumeraciones (`enum`)

Permite definir variantes fuertemente tipadas:

```bg
enum EventType:
    QUIT = 256,
    KEYDOWN = 257,
    KEYUP = 258,
```

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
