# Errores encontrados en Linux

Fecha: 2026-10-30  
Entorno de prueba comunicado: Linux x86-64, Python 3.13, llvmlite 0.50.0 (LLVM 22.1.0), Gram actualizado y VNMA 0.3.3.

> Alcance: hallazgos observados durante pruebas manuales de Bagron en Linux. No equivalen a una ejecución completa de la suite ni a una auditoría exhaustiva. Se distinguen defectos del compilador, limitaciones actuales y errores del programa de prueba.

## 1. Error de enlace al generar ejecutables Linux con constantes de cadena

**Severidad:** alta para ejecutables afectados.  
**Estado:** reproducido en las pruebas manuales; pendiente de corrección y regresión automatizada.

**Síntoma:** un programa Bagron con cadenas constantes puede compilar hasta archivo objeto, pero el enlace de un ejecutable Linux falla con un error similar a:

```text
relocation R_X86_64_32 cannot be used against local symbol
```

**Ruta de código relacionada:** `core/backend/llvm/targets.py`, función `resolve_target()`. Se crea el target machine con `codemodel='small'` y `opt=target_opt`, sin seleccionar explícitamente el modelo de relocación. Debe revisarse también el comando de enlace Linux para comprobar si Clang genera PIE por defecto.

**Hipótesis:** desajuste entre las relocaciones absolutas del objeto generado y el enlace PIE predeterminado del sistema. No se debe atribuir el problema a `char` o `chain` sin una reproducción aislada.

**Solución temporal verificada:** enlazar manualmente el objeto con `clang -no-pie`. Esto permite ejecutar el programa, pero renuncia a PIE y no constituye la solución definitiva.

**Corrección propuesta:** establecer explícitamente una política coherente para generación de objetos y enlace en Linux (por ejemplo, target machine con relocación PIC cuando se enlace como PIE), verificar las opciones del linker y probar el resultado en ejecutables Linux x86-64.

**Pruebas de regresión recomendadas:**
- Compilar y ejecutar un programa con `chain` y constantes globales de texto.
- Comprobar el enlace normal, sin `-no-pie` manual.
- Inspeccionar el objeto con `readelf -r` y el ejecutable con `readelf -h`.
- Ejecutar el mismo caso en perfiles `dev`, `prod` y `high`.

## 2. `@assembler` no disponible para Linux x86-64

**Severidad:** media; limitación de plataforma, no regresión confirmada.  
**Estado:** restricción explícita en el código.

**Síntoma:** al intentar utilizar `@assembler` en Linux, el compilador rechaza el target:

```text
Las funciones @assembler requieren el target Windows x64 en esta fase
```

**Ruta de código:** `core/compiler/prep.py`, función `_windows_x64_registers()`. La implementación valida que el triple sea Windows x64 y utiliza reglas de ABI y registros específicas de Windows.

**Impacto:** impide implementar directamente una instrucción `syscall` de Linux mediante `@assembler` con el mecanismo actual. Las llamadas a libc mediante `extern "c"` sí se probaron y funcionaron; **`write()` de libc no es una prueba de `syscall` directa**.

**Corrección propuesta:** añadir soporte independiente para la ABI System V AMD64 y los registros de argumentos de syscalls Linux, sin reutilizar las convenciones de Windows. Distinguir la ABI de funciones C de la ABI de `syscall` (por ejemplo, cuarto argumento en `r10` para `syscall`). Incluir pruebas de `@assembler` y de clobbers/registros.

## 3. Precauciones al leer entrada de Linux

**Clasificación:** error del prototipo de prueba; **no se atribuye a Bagron**.

Una primera versión del juego imprimía bytes nulos por escribir longitudes fijas sobre datos no inicializados y elegía una opción según el número de bytes leídos en lugar de su contenido.

**Solución en el programa de prueba:** usar `chain` para mensajes fijos, `char[]` para datos recibidos, respetar el número de bytes devueltos por `read()` y comparar el contenido de la entrada. El prototipo corregido pasó los casos de opciones 1, 2, 3, entrada inválida y entrada vacía.

## Validaciones que sí funcionaron

- Generación y ejecución de un ELF Linux x86-64 sencillo.
- Interoperabilidad con `read()` y `write()` de libc mediante `extern "c"`.
- Variables `char`, indexación de `char[]` y comparaciones de caracteres.
- Funciones, condiciones y códigos de salida en el juego de piedra, papel o tijera, **tras aplicar el enlace temporal con `-no-pie`**.

## Prioridad sugerida

1. Corregir la generación/enlace PIE en Linux y automatizar una prueba mínima.
2. Mantener separada la ampliación de `@assembler` a Linux AMD64.
3. Añadir ejemplos de entrada/salida con `chain` y `char[]` que respeten longitudes.

No se han aplicado cambios al compilador en este informe.
