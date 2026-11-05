# 05. Retorno y restricciones

## 1. Instrucción `return asm`

`return asm` no es un salto ASM libre ni una llamada a función. Indica que el bloque de ensamblador dejó el resultado listo en el registro de retorno (`EAX` / `RAX`) y que Bagron añadirá el epílogo y retorno ABI correspondiente.

Para retornos escalares, el archivo ASM generado empieza con un estado de
fallo (`mov eax, 1` en Intel o `movl $1, %eax` en AT&T) antes del cuerpo escrito.
El cuerpo debe sobrescribir `EAX`/`RAX` en todos los caminos que deban devolver
otro valor. En funciones `void` y `Never` no se inyecta ese estado inicial.

No escribas instrucciones `ret` dentro del bloque de ensamblador:

```bg
@assembler
func one() int32:
    #assembler "intel"
        mov eax, 1
    #end
    return asm
```

El renderizador de Bagron inserta automáticamente la instrucción `ret` al final de la rutina ensamblada.

---

## 2. Reglas según el tipo de retorno

| Tipo de retorno | Uso de `return` | Uso de `return asm` | Comportamiento |
| --- | --- | --- | --- |
| **Entero escalar** (`int32`, `int64`, etc.) | ❌ Prohibido con `#assembler` | ✅ **Requerido exactamente 1** | El bloque debe preparar el valor y devolver con `return asm`. |
| **`void`** | ⚠️ Opcional si hay `#assembler` | ❌ Prohibido | No hay valor de retorno. No se inyecta código de estado. |
| **`Never`** | ❌ Prohibido | ❌ Prohibido | Función divergente / que no retorna (ej. `exit`, abort, bucle infinito). No inyecta código de estado ni requiere retornos. |

### Ejemplo con `void`:
```bg
@assembler
func barrier() void:
    #assembler "intel"
        mfence
    #end
```

### Ejemplo con `Never`:
```bg
@assembler
public func exit(code: int32) Never:
    #assembler "att"
        movq $60, %rax
        syscall
    #end
```

---

## 3. Restricciones adicionales de tipos

1. **Tipos de retorno ASM:** El resultado de `return asm` debe ser un entero escalar. No se permiten arrays, punteros ni estructuras como retorno de `return asm`.
2. **Prohibición de `ret`:** El cuerpo ASM no puede contener instrucciones `ret` o `retq`, ya que entrarían en conflicto con la envoltura ABI generada por el compilador.
3. **Parámetros:** Los parámetros de una función ASM no pueden ser arrays. Los tipos expansivos (`Len_t`, `Size_t`, `Signed_t`, `Region_t`), `chain` y agregados no son una interfaz de registros soportada por esta fase; usa enteros escalares de 8 a 64 bits o punteros explícitos.
