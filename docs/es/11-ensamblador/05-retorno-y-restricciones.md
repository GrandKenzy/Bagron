# 05. Retorno y restricciones

## 1. Retorno implícito del bloque ASM

Un bloque de ensamblador no necesita una instrucción `return`. El resultado se
deja en el registro ABI correspondiente (`EAX` / `RAX`) y Bagron añade el
retorno de la rutina automáticamente.

Para retornos enteros escalares, el archivo ASM generado empieza con un estado de
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
```

El renderizador de Bagron inserta automáticamente la instrucción `ret` al final
de una rutina `void` o con retorno entero. Las funciones `Never` no reciben un
`ret` implícito: el bloque debe garantizar que no continúe la ejecución.

---

## 2. Reglas según el tipo de retorno

| Tipo de retorno | Uso de `return` | Comportamiento |
| --- | --- | --- |
| **Entero escalar** (`int32`, `int64`, etc.) | ❌ Prohibido con `#assembler` | El bloque prepara el valor y el retorno ABI es implícito. |
| **`void`** | ⚠️ Opcional | No hay valor de retorno ni código de estado. |
| **`Never`** | ❌ Prohibido | Función divergente / que no retorna. No inyecta código de estado ni `ret`. |

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

1. **Tipos de retorno ASM:** Una función ASM con resultado debe retornar un entero escalar. No se permiten arrays, punteros ni estructuras.
2. **Prohibición de `ret`:** El cuerpo ASM no puede contener instrucciones `ret` o `retq`, ya que entrarían en conflicto con el retorno ABI generado por el compilador.
3. **Parámetros:** Los parámetros de una función ASM no pueden ser arrays. Los tipos expansivos (`Len_t`, `Size_t`, `Signed_t`, `Region_t`), `chain` y agregados no son una interfaz de registros soportada por esta fase; usa enteros escalares de 8 a 64 bits o punteros explícitos.
