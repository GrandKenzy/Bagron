# Ensamblador preparado

## Índice

- [01. Flujo de compilación](01-flujo-de-compilacion.md)
- [02. Bloques de función](02-bloques-de-funcion.md)
- [03. Dialectos y sintaxis](03-dialectos-y-sintaxis.md)
- [04. Parámetros y ABI Windows x64](04-parametros-y-abi.md)
- [05. Retorno y restricciones](05-retorno-y-restricciones.md)
- [06. Ensamblador de módulo y condicionales](06-modulo-y-condicionales.md)
- [07. Errores, targets y depuración](07-errores-targets-y-depuracion.md)

`@assembler` declara una frontera insegura y `#prep assembler` guarda el
ensamblador crudo para que Clang lo valide antes de enlazarlo.

```bg
@assembler
func zero() int32:
    #prep assembler "gas-intel"
        xor eax, eax
    #end
    return asm
```

Los únicos dialectos aceptados son `gas-intel` y `att`:

```bg
@assembler
func zero_att() int32:
    #prep assembler "att"
        xorl %eax, %eax
    #end
    return asm
```

`gas-intel` usa sintaxis Intel de GAS/LLVM, no NASM. Los alias `intel`,
`intel-gas`, `gas_intel`, `at&t` y `att_syntax` fueron retirados.

Los parámetros pueden interpolarse con `{nombre}`. En Windows x64, los cuatro
primeros argumentos enteros usan `RCX`, `RDX`, `R8` y `R9`; el backend escoge el
alias de ancho según el tipo.

```bg
@assembler
func equal(left: int32, right: int32) int32:
    #prep assembler "gas-intel"
        cmp {left}, {right}
        jne different
        mov eax, 1
        different:
        xor eax, eax
    #end
    return asm
```

Un bloque de módulo no usa `return asm`:

```bg
#prep assembler module "gas-intel"
    .section .rodata,"a"
    answer:
        .long 42
#end
```

Los diagnósticos relacionan el archivo generado con la línea `.bg` mediante
`core/compiler/prep.py` y `core/backend/llvm/module.py`.
