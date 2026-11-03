# 05. Retorno y restricciones

`return asm` no es un salto ASM libre. Indica que el bloque dejó el resultado
en el registro de retorno y Bagron añadirá el retorno ABI. No escribas `ret` en
el bloque:

```bg
@assembler
func one() int32:
    #prep assembler "gas-intel"
        mov eax, 1
    #end
    return asm
```

Para resultados no `void` debe existir exactamente un `return asm`. Para una
función `void`, usa `return` y no `return asm`:

```bg
@assembler
func barrier() void:
    #prep assembler "gas-intel"
        mfence
    #end
    return
```

El resultado de `return asm` debe ser un entero escalar. No se permiten arrays,
punteros ni agregados como retorno ASM. El cuerpo preparado tampoco puede
contener instrucciones `ret`, porque el renderizador inserta el retorno final.

Los parámetros de una función preparada no pueden ser arrays. Los tipos
expansivos (`Len_t`, `Size_t`, `Signed_t`, `Region_t`), `chain` y agregados no
son una interfaz de registros soportada por esta fase; usa enteros escalares o
punteros explícitos.
