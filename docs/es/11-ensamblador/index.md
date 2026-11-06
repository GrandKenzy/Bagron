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

En Baremetal AMD64 se debe declarar `clause ABI "sysv_amd64"`. Baremetal no
selecciona una ABI implícita ni admite convenciones arbitrarias.

```bg
clause System "windows"
clause Arch "amd"

@assembler
func equal(left: int32, right: int32) int32:
    #assembler "intel"
        cmp ecx, edx
        jne different
        mov eax, 1
        jmp done
        different:
        xor eax, eax
        done:
    #end
    return asm
```

El ejemplo declara Windows x64 porque usa `ecx` y `edx`. En un target System V
la misma función debe usar `edi` y `esi` para sus dos parámetros.

Usa `@assembler` cuando la implementación completa de una función deba ser
nativa, por ejemplo para una instrucción o una frontera ABI concreta. Para una
API que ya existe en una biblioteca del sistema, declara su firma con
[`extern`](../05-externos/index.md) y deja que Bagron valide la declaración ABI
y el enlace sin duplicar la implementación en ASM.

Los bloques ASM solo pueden pertenecer a funciones `@assembler`; no existe un
bloque ASM independiente a nivel de módulo.

Los diagnósticos de ensamblado relacionan el archivo emitido directamente
con el número de línea del archivo fuente `.bg` original.
