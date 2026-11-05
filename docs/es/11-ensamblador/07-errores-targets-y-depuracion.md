# 07. Errores, targets y depuración

La fase de preparación valida la estructura antes de invocar Clang. Los
errores habituales son:

| Situación | Diagnóstico esperado |
| --- | --- |
| falta `#end` | el bloque `#assembler` no tiene cierre |
| `#assembler` fuera de una función | solo se permite dentro de una función `@assembler` |
| uso de `#prep` | la directiva fue retirada; usa `#assembler "intel"` o `#assembler "att"` |
| bloque sin `@assembler` | la función requiere `@assembler` |
| dialecto desconocido | usa `intel` o `att` |
| uso de `gas-intel` | el dialecto fue retirado; usa `intel` |
| `ret` dentro del cuerpo | `return asm` agrega el retorno ABI |
| función ASM en arquitectura no soportada | esta fase requiere arquitectura x86_64 (Windows x64 o System V AMD64) |

Si Clang rechaza una instrucción, el backend conserva el archivo generado y
relaciona la línea del `.asm` con la fuente `.bg`, la función y el dialecto.
Revisa primero el archivo bajo `build/prep/` para distinguir un error del
backend de un error de sintaxis ASM.

La generación y el ensamblado se realizan en el host; la disponibilidad de
`clang` es obligatoria cuando el proyecto contiene bloques ASM. El
objeto se enlaza después con el objeto LLVM de Bagron y debe respetar el target
seleccionado.
