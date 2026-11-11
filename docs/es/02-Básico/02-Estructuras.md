# Estructuras

| Tipo | Firma | Qué es |
|:---|:---|:---|
| `struct` | `struct Nombre:` | Agrupación nominal de campos con almacenamiento independiente. |
| `mold` | `mold Nombre:` | Vista nominal de almacenamiento superpuesto, similar a una unión. |
| `flags` | `flags Nombre TipoBase:` | Conjunto nominal de campos empaquetados por bits sobre un tipo base entero sin signo. |
| `enum` | `enum Nombre [TipoBase]:` | Conjunto nominal de miembros enteros con valores constantes. |
| `class` | `class Nombre [Padre]:` | Agregado nominal respaldado por un `struct`, con inicialización y métodos. |

Los campos se declaran con la forma `nombre: Tipo`.

## `struct`

Un `struct` agrupa varios campos bajo un nombre único. Cada campo conserva su
propio tipo y almacenamiento, y el conjunto se trata como un solo valor.
Los nombres de campo deben ser únicos. Un `struct` vacío se rechaza, los arrays
de campo deben tener dimensiones estáticas y no se permiten ciclos por valor;
la recursión mediante un puntero sí es posible. `chain` no puede declararse
como campo de un agregado.

### Firma

```bg
struct Nombre:
    campo: Tipo
    otro: OtroTipo
```

### Decoradores y especificadores compatibles

| Elemento | Forma | Función |
|:---|:---|:---|
| `packed` | `@packed` | Elimina el padding automático entre campos. |
| `volatile` | `volatile struct Nombre:` | Conserva los accesos al almacenamiento como operaciones volátiles. |
| `align` | `@align(N)` | Solicita una alineación explícita para el tipo. |

`@align(N)` recibe el valor de alineación solicitado para el `struct`.

## `mold`

Un `mold` define varias vistas nominales sobre un mismo bloque de
almacenamiento. Sus campos se superponen: leer o escribir un campo puede
interpretar los mismos bytes con otro tipo.

### Firma

```bg
mold Nombre:
    campo: Tipo
    otra_vista: OtroTipo
```

### Decoradores y especificadores compatibles

| Elemento | Forma | Función |
|:---|:---|:---|
| `packed` | `@packed` | Reduce el padding del almacenamiento superpuesto. |
| `align` | `@align(N)` | Solicita una alineación explícita para el tipo. |
| `volatile` | `volatile mold Nombre:` | Conserva los accesos al almacenamiento como operaciones volátiles. |

`mold` es apropiado cuando varias representaciones deben ocupar exactamente
la misma región de memoria; no crea almacenamiento independiente para cada
campo. El backend reserva una región del tamaño de la vista más grande y cada
campo se interpreta desde el inicio de esa región; no existe un tag que indique
qué vista se escribió. Los `mold` tampoco pueden estar vacíos.

## `flags`

Un `flags` empaqueta campos lógicos dentro de un tipo entero base explícito.
Cada campo ocupa únicamente el número de bits que declara, por lo que resulta
adecuado para estados, permisos y otras combinaciones compactas.

### Firma

```bg
flags Nombre TipoBase:
    campo: uBint<1> = 0
    estado: Bint<3> = 0
    activo: bool = false
```

El tipo base debe ser un entero estricto sin signo: `uint8`, `uint16`,
`uint32` o `uint64`. Los campos solo pueden ser `Bint`, `uBint` o `bool`.
`Bint` requiere al menos 2 bits; `uBint` puede ocupar desde 1 bit y `bool`
ocupa 1 bit lógico. Los tipos base con signo no se aceptan porque el
contenedor solo representa bits y no necesita interpretación signed.

La suma de los anchos de todos los campos debe coincidir exactamente con el
ancho del tipo base. Si faltan bits o se excede el ancho disponible, el
compilador rechaza el `flags`; los bits reservados deben declararse de forma
explícita, por ejemplo con un campo `uBint<N>` inicializado en cero.

### Decoradores y especificadores compatibles

| Elemento | Forma | Función |
|:---|:---|:---|
| `packed` | `@packed` | Mantiene el almacenamiento del conjunto sin padding adicional. |
| `align` | `@align(N)` | Solicita una alineación explícita para el contenedor. |
| `order_msb` | `@order_msb` | Asigna los campos comenzando por los bits más significativos. |
| `volatile` | `volatile flags Nombre TipoBase:` | Conserva los accesos al contenedor como operaciones volátiles. |

Los campos sin decorador se asignan desde los bits menos significativos.
`@order_msb` selecciona el orden contrario.

Los valores escritos en la declaración son los valores iniciales de los
campos. Un literal designado de `flags` comienza con todos los bits en cero y
solo escribe los campos designados; no reutiliza automáticamente esos valores
declarativos. Un bitfield no tiene dirección propia y no puede usarse con `$`.

## `enum`

Un `enum` es un tipo nominal que asocia nombres con valores enteros validados
durante la compilación. Su declaración completa es:

```bg
[public|private] enum Nombre [TipoBase]:
    MIEMBRO [= literal_entero],
    OTRO_MIEMBRO
```

Si se omite `TipoBase`, Bagron usa `int32`. También admite `int8`, `int16`,
`int32`, `int64`, `uint8`, `uint16`, `uint32`, `uint64`, `byte`, `isize` o
`usize`. No se permiten `bool`, `const`, punteros, arrays ni tipos expansivos.

### Valores y sintaxis

El primer miembro implícito vale `0`. Un valor explícito fija ese miembro y el
siguiente automático continúa desde ese valor más uno:

```bg
enum Estado uint8:
    INACTIVO,       ; 0
    ACTIVO = 4,     ; 4
    PAUSADO,        ; 5
    CANCELADO = 10, ; 10
    ARCHIVADO       ; 11
```

El valor explícito debe ser un literal entero, no una expresión, variable u
otro miembro. La coma final es opcional. Los nombres repetidos se rechazan,
pero los valores pueden repetirse; el compilador solo exige que cada valor
quepa en el rango de la base, incluidos los incrementos implícitos.

### Uso como tipo y límites actuales

El nombre se usa en variables, parámetros, retornos y campos:

```bg
enum Estado uint8:
    INACTIVO,
    ACTIVO = 4

struct Registro:
    estado: Estado
```

`Estado` es nominal: no se intercambia automáticamente con `uint8`, aunque
usen el mismo ancho, y `as` no ofrece una conversión general entre un enum y su
base. Sus miembros sí son valores constantes tipados, por lo que pueden usarse
en asignaciones, condiciones, argumentos, retornos y comparaciones:

```bg
estado: Estado = Estado.ACTIVO
es_activo: bool = estado == Estado.ACTIVO
```

El miembro conserva el tipo `Estado`, no el tipo entero de la base. Los enums
distintos tampoco se mezclan automáticamente, aunque compartan representación.

Un `enum` no es un agregado: no tiene campos, métodos ni literal `{ ... }`. En
el backend usa directamente el ancho y la ABI de su base, sin tag runtime ni
tabla de miembros. Un `struct` o `mold` puede contener un campo enum, pero la
reinterpretación de un `mold` sigue siendo responsabilidad de `mold`.

`enum` describe valores enteros nombrados; `flags` describe bits combinables.
Usa `flags` para permisos que puedan activarse simultáneamente y `enum` para
estados o códigos individuales. Consulta la [referencia dedicada de
`enum`](../07-estructuras%20struct,%20mold%20y%20flags/05-enum.md) para rangos,
visibilidad, ABI y diagnósticos.

## `class`

Una `class` es un agregado nominal respaldado por un `struct`. Sus atributos
se infieren de asignaciones `self.campo = valor` dentro de un único
`__init__` o `__frontend__`; no se declaran como campos sueltos en el cuerpo de
la clase. El inicializador debe devolver `void`. Una clase sin inicializador no
se puede construir, y declarar dos inicializadores es un error.

`__frontend__` recibe exactamente un parámetro visible y sirve como conversión
implícita de entrada. La herencia es simple y estática: una clase hija puede
tener un único padre, debe llamar a `super.__init__`, y el layout resultante
aplana los campos del padre y de la hija; no hay vtables ni despacho dinámico.
Los métodos de instancia reciben `self` de forma implícita, mientras que los
métodos `@static` se llaman a través de la clase y no reciben `self`.

Los nombres que empiezan por `_` son privados para la clase que los declara y
no quedan visibles para sus subclases. Las clases se retornan por valor.

Al destruir una instancia de clase con `Del`, el compilador realiza una limpieza
automática de su memoria (puesta a cero de todos sus campos). Si la clase implementa
el hook `__deletion__`, este se ejecuta por defecto justo *después* de dicha limpieza;
si se desea ejecutar antes de limpiar la memoria, el método se decora con `@before`.
Los literales agregados con campos designados (por ejemplo `Point{ .x = 10, .y = 20 }`)
permiten inicializaciones expresivas de agregados `struct`.
Para más detalles sobre destrucción y clases, consulta
[Frozen y destrucción](../06-clases/05-frozen-y-destruccion.md).

