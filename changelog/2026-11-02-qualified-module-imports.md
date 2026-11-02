# Imports de módulos cualificados

Los imports de módulos ya no aplanan sus declaraciones públicas en el ámbito
del módulo importador. Ahora:

```bg
import time

func main() int32:
    return time.now()
```

También se puede elegir otro namespace con `import time as clock` y usar
`clock.now()`. Los imports selectivos conservan sus bindings directos porque
expresan explícitamente esa intención:

```bg
import { now as current_time } from time
```

La resolución frontend mantiene los límites de módulo y el backend prepara los
alias cualificados antes de emitir cuerpos, incluidos los módulos importados
que llaman a otros módulos.
