# 02. Bloques de función

Un bloque de función debe estar dentro de una función y llevar un dialecto
entre comillas:

```bg
@assembler
func zero() int32:
    #assembler "intel"
        xor eax, eax
    #end
```

`#assembler` se indenta dentro de la función. El bloque puede aparecer una sola vez
por función `@assembler` y se cierra con `#end`. La función debe tener la
declaración `@assembler`; si el bloque existe sin el decorador, el frontend lo
rechaza.

Los bloques de varias funciones del mismo archivo `.bg` se escriben en una sola
unidad `.asm`. Esto no cambia su independencia semántica ni su contrato ABI:
cada función conserva su símbolo, dialecto y retorno. Los módulos `.bg` distintos
siguen generando unidades ASM y objetos separados.

La función solo puede contener el bloque ASM. No añadas variables, condiciones,
llamadas Bagron ni otro bloque dentro de ese cuerpo. El retorno ABI es implícito.
Para funciones `@assembler` sin bloque ASM se conserva el cuerpo normal y sus
reglas de `return`.

`@assembler` implica `unsafe`: una función segura no puede cruzar esta frontera
de bajo nivel sin declararlo.
