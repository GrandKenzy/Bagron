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

Las rutas entre comillas se resuelven únicamente en `project_root/libs`. Para
dependencias distribuidas con Bagron puede usarse un nombre global sin comillas,
como `library gnulibrary as gnu`; esa forma busca únicamente
`BAGRON_ROOT/libs/gnulibrary.lib`. `lib/` o una ruta junto a `main.bg` no son
raíces implícitas de librerías; separar los módulos fuente locales, `libs/` y
`bins/` evita
resolver artefactos obsoletos por accidente.
