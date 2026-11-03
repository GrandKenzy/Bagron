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

La resolución de `.lib` usa únicamente `project_root/libs`. `lib/` o una ruta
junto a `main.bg` no son raíces implícitas de librerías; separar `modules/`,
`libs/` y `bins/` evita resolver artefactos obsoletos por accidente.
