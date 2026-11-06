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
campo.

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

## `enum`

Un `enum` es un tipo nominal cuyos miembros tienen valores enteros constantes.
Si no se indica un tipo base, se usa `int32`; también puede declararse
cualquier tipo entero escalar (`int8`/`int16`/`int32`/`int64`, `uint8`/`uint16`/
`uint32`/`uint64`, `byte`, `isize` o `usize`). El tipo base no puede ser
`const`, puntero ni array.

```bg
enum Estado uint8:
    INACTIVO,
    ACTIVO = 4,
    PAUSADO
    ; valores: 0, 4 y 5
```

Los miembros automáticos comienzan en `0`; un valor explícito fija el miembro y
el siguiente automático continúa desde ese valor más uno. La coma final en el
último miembro es opcional. Los miembros
duplicados y los valores fuera del rango del tipo base se rechazan. En el
backend, el `enum` conserva su nombre nominal, pero usa la representación y el
ancho del tipo base.

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

