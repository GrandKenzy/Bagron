# Ensamblador de funciones

## Índice

- [01. Flujo de compilación](01-flujo-de-compilacion.md)
- [02. Bloques de función](02-bloques-de-funcion.md)
- [03. Dialectos y sintaxis](03-dialectos-y-sintaxis.md)
- [04. Parámetros y ABI Windows x64](04-parametros-y-abi.md)
- [05. Retorno y restricciones](05-retorno-y-restricciones.md)
- [06. Condicionales y bloques ASM](06-modulo-y-condicionales.md)
- [07. Errores, targets y depuración](07-errores-targets-y-depuracion.md)

`@assembler` declara una frontera insegura y `#assembler` guarda el
ensamblador crudo de una función para que Clang lo valide antes de enlazarlo.

```bg
@assembler
func zero() int32:
    #assembler "intel"
        xor eax, eax
    #end
    return asm
```

Los únicos dialectos aceptados son `intel` y `att`:

```bg
@assembler
func zero_att() int32:
    #assembler "att"
        xorl %eax, %eax
    #end
    return asm
```

`intel` usa sintaxis Intel de GAS/LLVM, no NASM. `att` conserva la sintaxis
AT&T de GAS/LLVM. No existen alias de compatibilidad.

Los parámetros no se interpolan en el texto ASM. La función recibe sus
argumentos según la ABI del target y el cuerpo debe usar directamente los
registros correspondientes. En Windows x64, los cuatro primeros argumentos
enteros usan `RCX`, `RDX`, `R8` y `R9`; en System V AMD64, los seis primeros usan
`RDI`, `RSI`, `RDX`, `RCX`, `R8` y `R9`.

```bg
@assembler
func equal(left: int32, right: int32) int32:
    #assembler "intel"
        cmp ecx, edx
        jne different
        mov eax, 1
        different:
        xor eax, eax
    #end
    return asm
```

Los bloques ASM solo pueden pertenecer a funciones `@assembler`; no existe un
bloque ASM independiente a nivel de módulo.

Los diagnósticos relacionan el archivo generado con la línea `.bg` mediante
`core/compiler/prep.py` y `core/backend/llvm/module.py`.
