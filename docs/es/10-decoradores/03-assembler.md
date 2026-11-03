# 03. `@assembler`

`@assembler` autoriza que una función contenga un bloque `#prep assembler`.
También cruza automáticamente la frontera `unsafe`:

```bg
@assembler
func zero() int32:
    #prep assembler "gas-intel"
        xor eax, eax
    #end
    return asm
```

El bloque se extrae antes del parser de Bagron. Los dialectos activos son
`gas-intel` y `att`; los alias ASM legacy no forman parte de la sintaxis.

Una función `@assembler` con bloque solo puede contener ese bloque y el retorno
correspondiente. Para un resultado escalar no `void` debe haber exactamente un
`return asm`; una función `void` no puede usar `return asm`:

```bg
@assembler
func fence() void:
    #prep assembler "att"
        mfence
    #end
    return
```

`return asm` también exige que la función sea `@assembler` y retorne un entero
escalar. La función puede tener como máximo un bloque de ensamblador. El
compilador no verifica que las instrucciones respeten la ABI; los registros,
clobbers y restricciones son responsabilidad del autor.
