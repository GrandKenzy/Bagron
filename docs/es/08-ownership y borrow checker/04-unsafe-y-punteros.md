# 04. `@unsafe` y la frontera de punteros

`@unsafe` marca una función que asume la responsabilidad por la procedencia,
la vida y los límites de una dirección:

```bg
@unsafe
func write(pointer *: int32) void:
    (pointer) = 42
    return
```

Una función segura no puede llamar a una función `@unsafe`. Indexar un puntero
crudo, desreferenciar una dirección obtenida de un `mold` o acceder a un
agregado mediante un puntero cuya procedencia no puede demostrarse son casos
que cruzan esta frontera.

`@unsafe` no valida la dirección, no convierte `Null` en una dirección válida,
no añade límites a un puntero y no relaja las reglas de tipos, `const`, arrays,
`buffer` o `unique`. Mantén el bloque inseguro pequeño y deja el contrato de
longitud y vida junto a la función que lo necesita.
