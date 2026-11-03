# 02. Bloques de función

Un bloque de función debe estar dentro de una función y llevar un dialecto
entre comillas:

```bg
@assembler
func zero() int32:
    #prep assembler "gas-intel"
        xor eax, eax
    #end
    return asm
```

`#prep` se indenta dentro de la función. El bloque puede aparecer una sola vez
por función `@assembler` y se cierra con `#end`. La función debe tener la
declaración `@assembler`; si el bloque existe sin el decorador, el frontend lo
rechaza.

La función solo puede contener el bloque ASM y el retorno que corresponda. No
añadas variables, condiciones, llamadas Bagron ni otro bloque dentro de ese
cuerpo. Para funciones sin bloque ASM, `@assembler` sigue exigiendo un único
`return`, pero no permite `return asm`.

`@assembler` implica `unsafe`: una función segura no puede cruzar esta frontera
de bajo nivel sin declararlo.
