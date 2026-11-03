# 04. Parámetros y ABI Windows x64

En esta fase, las plantillas de funciones `@assembler` requieren target Windows
x64. Los cuatro primeros argumentos enteros o punteros se asocian a `RCX`,
`RDX`, `R8` y `R9`; Bagron elige el alias de ancho según el tipo:

| Posición | 64 bits | 32 bits | 16 bits | 8 bits |
| --- | --- | --- | --- | --- |
| 1 | `rcx` | `ecx` | `cx` | `cl` |
| 2 | `rdx` | `edx` | `dx` | `dl` |
| 3 | `r8` | `r8d` | `r8w` | `r8b` |
| 4 | `r9` | `r9d` | `r9w` | `r9b` |

Los argumentos desde la quinta posición se leen en la pila: `[rsp + 0x28]` en
`gas-intel` y `0x28(%rsp)` en `att`, con ocho bytes por posición posterior.

Los nombres de parámetros se interpolan con `{nombre}`:

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

El placeholder se reemplaza antes de ensamblar. Debe ser un identificador que
exista en la firma; `{{` y `}}` producen llaves literales. Los parámetros deben
tener nombre, no pueden ser arrays y deben tener tipos enteros compatibles de
hasta 64 bits o punteros.
