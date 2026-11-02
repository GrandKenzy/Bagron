# Imports de constantes globales

Los módulos pueden exportar constantes globales y los módulos importadores
pueden leerlas sin una declaración `global`:

```bg
; sdl_init.bg
public SDL_INIT_AUDIO: const uint32 = 0x00000010

; _main.bg
import { SDL_INIT_AUDIO } from sdl_init
func main() int32:
    if SDL_INIT_AUDIO == 16:
        return 0
    return 1
```

También se admite la forma cualificada `sdl_init.SDL_INIT_AUDIO`. El enlace se
realiza antes de validar inicializadores globales, por lo que una constante
importada puede inicializar otra constante. Los globals mutables continúan
ocultos en funciones hasta que se declara `global nombre` explícitamente.
