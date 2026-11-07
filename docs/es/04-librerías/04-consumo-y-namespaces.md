# Consumo, aliases y visibilidad

El alias de una librería se convierte en namespace cualificado:

```bg
library "Math.lib" as M

func main() int32:
    return M.square(5)
```

Los módulos internos de la librería no se mezclan con los módulos fuente del
proyecto consumidor. La tabla pública conserva funciones, globals, tipos,
arrays y firmas expansivas.

Las declaraciones privadas no pueden consumirse:

```bg
library "Math.lib" as M

func main() int32:
    ; M.internal() sería rechazado si no es public.
    return M.square(5)
```

Las rutas entre comillas se resuelven en el `libs/` del propietario. En la
aplicación es `project_root/libs`; dentro de un paquete es el `libs/` de ese
paquete. Para dependencias distribuidas con Bagron puede usarse un nombre global
sin comillas, como `library gnulibrary as gnu`; esa forma busca únicamente
`BAGRON_ROOT/libs/gnulibrary.lib`. Los `import` de la aplicación solo buscan en
sus módulos y raíz de proyecto, mientras que un paquete solo puede buscar en su
propio árbol. `lib/` o una ruta junto a `main.bg` no son raíces implícitas de
librerías; separar los módulos fuente locales, `libs/` y `bins/` evita resolver
artefactos obsoletos por accidente.

## Tipos e importaciones explícitas

Los tipos declarados dentro de una librería no se filtran automáticamente al
ámbito global del código consumidor. Para utilizarlos sin cualificación, deben
importarse explícitamente desde el alias de la librería:

```bg
library time as Time
import { DateTime, Duration, Stopwatch } from Time

func main() int32:
    dt: DateTime = Time.now_datetime()
    return 0
```

Si en la raíz del proyecto existe una carpeta con el mismo identificador que la
librería consumida (por ejemplo, una carpeta `time/`), la declaración
`import { ... } from Time` resuelve prioritariamente el alias vinculado por
`library time as Time` en lugar del directorio en disco.

## Espacio de nombres y prevención de colisiones

Todos los módulos que componen una librería comparten el espacio de exportación
público cuando la librería se consume bajo su alias cualificado. Al empaquetar con
`bagron library`, el compilador valida y rechaza exportaciones de símbolos
públicos no-método duplicados entre módulos distintos. Se recomienda utilizar
prefijos consistentes por submódulo (por ejemplo, `duration_*`, `stopwatch_*`)
para mantener la claridad y evitar colisiones entre áreas funcionales.
