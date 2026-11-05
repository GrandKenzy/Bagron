# 03. `@assembler`

`@assembler` autoriza que una función contenga un bloque `#assembler`.
También cruza automáticamente la frontera `unsafe`:

```bg
@assembler
func zero() int32:
    #assembler "intel"
        xor eax, eax
    #end
    return asm
```

El bloque se extrae antes del parser de Bagron. Los dialectos activos son
`intel` y `att`; los alias ASM legacy no forman parte de la sintaxis.

Una función `@assembler` con bloque solo puede contener ese bloque y el retorno
correspondiente:
- Para un resultado escalar entero no `void` debe haber exactamente un `return asm`.
- Una función `void` no puede usar `return asm` (el `return` estándar es opcional con `#assembler`).
- Una función `Never` no puede usar ni `return` ni `return asm`:

```bg
@assembler
public func exit(code: int32) Never:
    #assembler "att"
        movq $60, %rax
        syscall
    #end
```

`return asm` también exige que la función sea `@assembler` y retorne un entero
escalar. La función puede tener como máximo un bloque de ensamblador. El
compilador no verifica que las instrucciones respeten la ABI; los registros,
clobbers y restricciones son responsabilidad del autor.

`@assembler` representa una implementación completa escrita en ASM. Para
funciones que solo exponen una API nativa ya implementada por una biblioteca,
usa [`extern`](../05-externos/index.md): así se valida la firma ABI y el enlace
sin mantener un archivo ASM separado por cada función externa.
