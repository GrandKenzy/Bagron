# Directivas de enlace y librerías

## `#link`

`#link` añade un directorio local para buscar bibliotecas nativas:

```bg
#link "./bins"
#link "vendor/SDL3/bins"
```

La directiva solo se permite en el módulo de entrada. La ruta es relativa al
archivo que la contiene, debe existir como directorio y debe quedar dentro de
la raíz del proyecto. Las rutas absolutas, vacías, que apunten a archivos o
que escapen mediante `..` se rechazan.

`#link` no declara símbolos. Combínalo con `extern` para describir la firma y
el dominio ABI de la biblioteca:

```bg
extern windows "SDL3":
    SDL_Init(flags: uint32) int32
```

Los módulos importados no pueden inyectar directorios de enlace en el proyecto
principal.

## `library`

`library` solicita una librería Bagron empaquetada y también solo se permite en
el módulo de entrada:

```bg
library "Math.lib" as Math
import Math
```

La forma exacta es `library "ruta.lib" as Alias`. El archivo se busca en
`libs/` del proyecto; no se aceptan rutas absolutas ni un alias vacío. `library`
se extrae antes del parser y la importación posterior usa el namespace o alias
de sus símbolos públicos.

No confundas `library` con `#link`: el primero carga un paquete `.lib` de
Bagron; el segundo solo aporta una carpeta al enlazador nativo.
