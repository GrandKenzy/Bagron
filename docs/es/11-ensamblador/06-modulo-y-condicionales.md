# 06. Ensamblador de módulo y condicionales

Un bloque de módulo no pertenece a ninguna función y no usa `return asm` ni
placeholders:

```bg
#prep assembler module "gas-intel"
    .section .rodata,"a"
    answer:
        .long 42
#end
```

Debe estar al nivel del módulo. Se escribe como una unidad ASM independiente,
sin que Bagron añada símbolo de función, prólogo, epílogo o contrato de
registros. Las llaves `{` y `}` están prohibidas en este modo.

El preprocesador admite condiciones simples para seleccionar declaraciones
Bagron:

```bg
#if OS, "windows"
func fence() void:
    return
#elif ARCH, "amd"
func fence() void:
    return
#end
```

Se admiten `#if`, `#elif`, `#else` y `#end` con `OS` o `ARCH`. Los bloques
condicionales no se pueden anidar. Como `#end` es también el cierre de
`#prep`, no coloques un bloque de función o de módulo dentro de un `#if`: su
`#end` cerraría el bloque condicional antes de la extracción ASM. Selecciona
el módulo o la fuente apropiada antes de preparar el ensamblador. Ningún
`#end` debe recibir argumentos.
