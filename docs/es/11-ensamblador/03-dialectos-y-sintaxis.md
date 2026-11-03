# 03. Dialectos y sintaxis

Los dialectos canónicos son `gas-intel` y `att`:

```bg
@assembler
func zero_att() int32:
    #prep assembler "att"
        xorl %eax, %eax
    #end
    return asm
```

`gas-intel` usa sintaxis Intel de GAS/LLVM, no sintaxis NASM. `att` usa
registros con `%`, operandos en orden AT&T y sufijos de instrucción cuando
corresponda.

Se rechazan `nasm`, `intel`, `intel-gas`, `gas_intel`, `intel-nasm`, `at&t` y
`att_syntax`. Los alias retirados no vuelven a ser compatibles por
normalización.

El bloque se entrega a Clang como ensamblador textual. Bagron no convierte
mnemonics, valida registros ni traduce la semántica entre dialectos; escribe la
directiva de sintaxis adecuada y deja la validación final a Clang.

```bg
@assembler
func add_one(value: int32) int32:
    #prep assembler "gas-intel"
        lea eax, [{value} + 1]
    #end
    return asm
```
