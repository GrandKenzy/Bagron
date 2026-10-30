# Módulos e `import`

Un módulo Bagron es un archivo `.bg`. El archivo ejecutable suele ser
`_main.bg` o `main.bg` y puede importar otros módulos antes de declarar su
`func main() int32:`.

## Formas canónicas

Un import usa un identificador de módulo simple:

```bg
import math
import standard as std
import { doble as twice } from math
```

Las tres formas significan:

- `import math`: hace disponibles las declaraciones públicas de `math` con
  sus nombres originales.
- `import standard as std`: permite usar las declaraciones públicas mediante
  el nombre cualificado, por ejemplo `std.print(...)`.
- `import { doble as twice } from math`: importa solo `doble` con el nombre
  local `twice`.

El alias de una función conserva exactamente su firma original. Esto incluye
los parámetros expansivos `Len_t` y `Size_t`, que el compilador sigue
inyectando a partir del argumento real:

```bg
; arrays.bg
func total(values: int32[], length: Len_t, size: Size_t) int32:
    return 0

; _main.bg
import arrays as a

func main() int32:
    values: int32[3] = {1, 2, 3}
    return a.total(values)
```

En este ejemplo la llamada recibe internamente la longitud `3` y el tamaño de
elemento `4`, sin que el código fuente tenga que escribirlos.

## Resolución de archivos

Para `import nombre`, el compilador busca `nombre.bg` o `nombre/main.bg` en
este orden:

1. el directorio del módulo que contiene el import;
2. la raíz del proyecto, que es el directorio del archivo ejecutable;
3. `lib/` en la raíz del proyecto;
4. `libs/` en la raíz del proyecto.

El nombre debe ser un identificador simple ASCII (`A-Z`, `a-z`, `0-9` y `_`,
sin comenzar por un número). No se aceptan extensiones, separadores, rutas
absolutas ni componentes `..` en la sintaxis de `import`.

Cada ruta encontrada se canonicaliza antes de cargarse. Un enlace simbólico o
una ruta alternativa que termine fuera de la raíz del proyecto se rechaza.
Esto evita que un módulo importado lea código arbitrario fuera del proyecto y
permite detectar el mismo archivo aunque se haya escrito con rutas distintas.

## Target por módulo

El módulo de entrada selecciona el target de la compilación. La forma canónica
para fijarlo es:

```bg
clause System 'windows'
clause Arch 'amd'
```

`System` acepta `windows`, `linux`, `baremetal` o `auto`; `Arch` acepta
`auto`, `x86`, `amd`, `arm` o un triple LLVM. `auto` significa el target del
host. Para `baremetal` también se debe declarar el protocolo de arranque:

```bg
clause System 'baremetal'
clause Arch 'amd'
clause Boot 'multiboot2'
```

`Boot` acepta `none`, `multiboot2`, `uefi`, `opensbi`, `dtb` o `custom`.
`none` genera únicamente la imagen plana; `multiboot2` selecciona el flujo
ELF + `ld.lld` + ISO GRUB y actualmente solo es compatible con x86/i386 y
x86-64. Los demás perfiles se validan para su arquitectura, pero el backend
los marcará como no implementados hasta que se añada su empaquetador.

Un sistema `linux` o `windows` no puede declarar un protocolo `Boot` distinto
de `none`. Un target `baremetal` requiere `Boot` explícito, incluso si se usa
`none`. Si `multiboot2` solicita herramientas que no existen en `PATH` o en
WSL, la compilación termina con un error explícito.

`System 'baremetal'` tampoco admite `extern` de librerías del sistema. Esa
declaración depende del runtime y linker del sistema operativo; para símbolos
propios del kernel se debe usar un módulo ASM.

Cada módulo importado se comprueba contra el target seleccionado por el módulo
de entrada. Un `System` o `Arch` explícito incompatible rechaza la compilación
antes de validar firmas y cuerpos. Las cláusulas de target de un import no
pueden cambiar el target global del backend.

Si un módulo omite `System`, queda agnóstico para el sistema; si omite `Arch`,
queda agnóstico para la arquitectura; y si omite `Boot` dentro de un proyecto
bare-metal, queda agnóstico para el protocolo de arranque. El import se permite
en esos casos, pero el compilador emite un warning para dejar constancia de la
dimensión omitida.
El módulo de entrada sin una de esas cláusulas también recibe el warning y usa
`auto` para esa dimensión.

Los ciclos también son errores:

```text
_main.bg -> a.bg -> b.bg -> a.bg
```

El compilador informa el ciclo y no continúa con un árbol parcialmente
resuelto.

## Visibilidad

Las declaraciones son públicas por defecto. `private` limita una declaración
al módulo que la contiene:

```bg
; secret.bg
private func secret() int32:
    return 7

public func answer() int32:
    return secret()
```

Otro módulo puede importar `answer`, pero no puede llamar `secret`, declarar
`global secret` ni construir un tipo `private` del módulo. La misma regla se
aplica a funciones, variables, `struct`, `mold`, `flags`, `enum`, `class` y
métodos.

Una declaración `private` no desaparece del archivo compilado: sigue siendo
necesaria para validar el cuerpo de su propio módulo. La restricción se aplica
al resolver usos desde otro módulo, incluso cuando el compilador ha aplanado
internamente el árbol de módulos.

## Errores que deben revisarse

El compilador debe rechazar todos estos casos:

- módulo inexistente o con una extensión distinta de `.bg`;
- nombre de módulo con ruta, extensión o traversal;
- archivo importado fuera de la raíz del proyecto;
- ciclo de imports;
- símbolo no público en un import selectivo;
- alias repetido dentro del mismo import;
- alias que ya apunta a otro símbolo;
- llamada a una función privada desde otro módulo;
- acceso `global` a una variable privada;
- uso o construcción de un tipo privado desde otro módulo.

La resolución de imports ocurre antes de la validación semántica de cuerpos:
primero se cargan los módulos, luego se registran todas las firmas y tipos, y
por último se validan los cuerpos. Así las llamadas pueden aparecer antes o
después de su definición, pero nunca saltan las reglas de visibilidad ni de
firma.
