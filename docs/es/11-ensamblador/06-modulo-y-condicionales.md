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
#endif
```

Se admiten `#if`, `#elif`, `#else` y `#endif` con `OS` o `ARCH`. Los bloques
condicionales no se pueden anidar. `#end` queda reservado para cerrar un bloque
`#assembler`, por lo que ambos cierres ya no son ambiguos.
