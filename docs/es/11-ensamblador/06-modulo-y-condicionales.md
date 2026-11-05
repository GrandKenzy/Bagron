# 06. Condicionales y bloques ASM

Los bloques ASM solo pueden estar dentro de funciones `@assembler`. No existe
una unidad ASM independiente a nivel de módulo.

El preprocesador admite condiciones simples para seleccionar declaraciones
Bagron:

```bg
#if OS, "windows"
func fence() void:
    return
#elif ARCH, "amd"
func fence() void:
    return
#end
```

Se admiten `#if`, `#elif`, `#else` y `#end` con `OS` o `ARCH`. Los bloques
condicionales no se pueden anidar. Como `#end` también cierra un bloque
`#assembler`, no coloques un bloque de función dentro de un `#if`: selecciona
la rama antes de extraer el ensamblador. Ningún `#end` debe recibir argumentos.
