# Directivas de ensamblador

`#prep assembler` extrae ensamblador textual antes del parser:

```bg
@assembler
func zero() int32:
    #prep assembler "gas-intel"
        xor eax, eax
    #end
    return asm
```

También existe `#prep assembler module "dialecto"` para una unidad ASM a nivel
de módulo. Los dialectos canónicos son `gas-intel` y `att`; los placeholders
de parámetros solo funcionan dentro de una función.

El bloque de función exige `@assembler`, y `return asm` deja que Bagron añada
el retorno ABI. El módulo no usa `return asm` ni puede interpolar parámetros.

La directiva se documenta con detalle en [Ensamblador preparado](../11-ensamblador/index.md),
incluidos extracción, ABI, targets, restricciones y diagnósticos de Clang.
