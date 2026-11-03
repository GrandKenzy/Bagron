# Imports y namespaces

Un módulo Bagron es un archivo `.bg`. `import` carga otro módulo y deja
disponibles sus definiciones públicas. El nombre del módulo debe ser un
identificador simple, sin extensión, rutas ni componentes `..`.

## Import con namespace

```bg
import math
import standard as std

func main() int32:
    return math.double(21) + std.answer()
```

Sin alias, el namespace usa el nombre del módulo. Con `as`, usa el alias
declarado. Las definiciones no se filtran al ámbito local: se acceden como
`namespace.nombre`.

## Import selectivo

```bg
import { double as twice, answer } from math

func main() int32:
    return twice(answer)
```

El import selectivo crea nombres locales directos. Cada símbolo debe ser
público y un alias local no puede repetirse ni chocar con otro símbolo.
Funciones, variables globales y tipos públicos pueden seleccionarse.

## Resolución de archivos

Para `import nombre`, el compilador busca:

1. `nombre.bg` o `nombre/main.bg` junto al módulo importador cuando este vive
   bajo `modules/`;
2. `modules/nombre.bg` o `modules/nombre/main.bg` en la raíz del proyecto;
3. el mismo patrón en la raíz del proyecto como fallback para proyectos
   antiguos.

La ruta final debe permanecer dentro de la raíz del proyecto. `libs/` no es una
raíz implícita para módulos `.bg`; se reserva para archivos `.lib` declarados
con `library`.

## Exportaciones y privacidad

Las declaraciones son públicas por defecto:

```bg
; math.bg
private func helper() int32:
    return 1

public func answer() int32:
    return helper()
```

Otro módulo puede importar `answer`, pero no `helper`. La privacidad se
comprueba también para variables, tipos, clases, agregados y funciones
externas. Un símbolo privado sigue existiendo para validar su propio módulo;
simplemente no forma parte de sus exportaciones.

## Firmas y ciclos

Un alias conserva la firma original, incluidos los parámetros expansivos:

```bg
; arrays.bg
func total(values: int32[], length: Len_t, size: Size_t) int32:
    return length

; main.bg
import { total as sum } from arrays

func main() int32:
    values: int32[3] = {1, 2, 3}
    return sum(values)
```

El llamador no escribe `Len_t` ni `Size_t`; la expansión se conserva al
resolver el alias. Los ciclos de imports se rechazan, por ejemplo:

```text
main.bg -> a.bg -> b.bg -> a.bg
```

La carga ocurre antes de validar los cuerpos: primero se resuelve el árbol,
después se registran firmas y tipos, y finalmente se comprueban los usos y la
visibilidad.
