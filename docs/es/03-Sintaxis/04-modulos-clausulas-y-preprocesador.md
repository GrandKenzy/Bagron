# Módulos, cláusulas y preprocesador

## Guías relacionadas

- [Directivas condicionales](06-directivas-condicionales.md)
- [Directivas de enlace y librerías](07-directivas-de-enlace-y-librerias.md)
- [Cláusulas de target y configuración](08-clausulas-de-target.md)
- [Directivas de ensamblador](09-directivas-de-ensamblador.md)
- [Imports y namespaces](10-imports-y-namespaces.md)

## Imports

```bg
import math
import math as m
import { triple as times_three } from math
```

Los imports simples buscan módulos `.bg` bajo `modules/` y conservan un
namespace. Los imports selectivos enlazan símbolos `public` con el alias local.
`private` sigue bloqueando el acceso aunque el módulo se haya cargado.

## Cláusulas de target

```bg
clause System 'windows'
clause Arch 'amd'
clause Optimizations 'prod'
```

`baremetal` requiere además `Boot` explícito:

```bg
clause System 'baremetal'
clause Arch 'amd'
clause Boot 'none'
```

Los módulos importados se comparan con el target del módulo de entrada.

## Preprocesador

Las condiciones se resuelven antes del lexer de Bagron y no pueden anidarse:

```bg
#if OS, "windows"
func platform() int32:
    return 1
#elif ARCH, "amd"
func platform() int32:
    return 2
#else
func platform() int32:
    return 0
#end
```

Solo se admiten `OS` y `ARCH`, con las directivas `#if`, `#elif`, `#else` y
`#end`. Una rama no seleccionada no se analiza como código Bagron.
