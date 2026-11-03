# 07. Errores, targets y depuración

La fase de preparación valida la estructura antes de invocar Clang. Los
errores habituales son:

| Situación | Diagnóstico esperado |
| --- | --- |
| falta `#end` | el bloque preparado no tiene cierre |
| `#prep` fuera de una función | solo se permite dentro de una función, salvo `module` |
| bloque sin `@assembler` | la función requiere `@assembler` |
| dialecto desconocido | usa `gas-intel` o `att` |
| placeholder inexistente | el parámetro no existe en la firma |
| `ret` dentro del cuerpo | `return asm` agrega el retorno ABI |
| función ASM en otro target | esta fase requiere Windows x64 |

Si Clang rechaza una instrucción, el backend conserva el archivo generado y
relaciona la línea del `.asm` con la fuente `.bg`, la función, el dialecto y la
línea del `#prep`. Revisa primero el archivo bajo `build/prep/` para distinguir
un error de expansión de parámetros de un error de sintaxis ASM.

La generación y el ensamblado se realizan en el host; la disponibilidad de
`clang` es obligatoria cuando el proyecto contiene bloques preparados. El
objeto se enlaza después con el objeto LLVM de Bagron y debe respetar el target
seleccionado.
