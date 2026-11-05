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
| ABI Baremetal ausente | Baremetal AMD64 requiere `clause ABI "sysv_amd64"` explícita |
| `ABI` fuera de Baremetal | la cláusula solo se permite con `System "baremetal"` |
| `ret` dentro del cuerpo | `return asm` agrega el retorno ABI |
| función ASM en arquitectura no soportada | esta fase requiere arquitectura x86_64 (Windows x64 o System V AMD64) |
| etiquetas no locales repetidas | cada etiqueta `nombre:` debe ser única dentro del archivo `.bg`; usa `.L...` o nombres distintos |

Si Clang rechaza una instrucción, el backend conserva el archivo generado y
relaciona el rango correspondiente del `.asm` agrupado con la fuente `.bg`, la
función y el dialecto. Las etiquetas locales `.L...` y las etiquetas numéricas
de GAS no participan en la detección de colisiones del agrupamiento.
Revisa primero el archivo bajo `build/prep/` para distinguir un error del
backend de un error de sintaxis ASM.

La generación y el ensamblado se realizan en el host; la disponibilidad de
`clang` es obligatoria cuando el proyecto contiene bloques ASM. El
objeto se enlaza después con el objeto LLVM de Bagron y debe respetar el target
seleccionado.
