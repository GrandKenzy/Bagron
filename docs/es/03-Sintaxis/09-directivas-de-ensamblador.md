# Directivas de ensamblador

`#assembler` extrae ensamblador textual antes del parser:

```bg
@assembler
func zero() int32:
    #assembler "intel"
        xor eax, eax
    #end
```

Los dialectos canónicos son `intel` y `att`. Los parámetros se reciben en los
registros de la ABI y no se interpolan en el texto ASM. No existen bloques ASM
a nivel de módulo.

El bloque de función exige `@assembler`; Bagron añade automáticamente el
retorno ABI al terminar el bloque.

La directiva se documenta con detalle en [Ensamblador de funciones](../11-ensamblador/index.md),
incluidos extracción, ABI, targets, restricciones y diagnósticos de Clang.
