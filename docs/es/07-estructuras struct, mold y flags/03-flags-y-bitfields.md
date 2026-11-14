# 03. `fields` y limbs

`fields` agrupa limbs manuales dentro de un agregado nominal:

```bg
@signed
fields Permissions:
    read: Bint(1)
    write: Bint(1)
    reserved: Bint(6)

func can_write(value: Permissions) bool:
    return value.write == 1
```

Cada campo debe ser `Bint(N)` con `N >= 1`. El almacenamiento conserva los
limbs como miembros independientes y no existe un contenedor entero implícito.

`@signed` añade un bit oculto para el signo del agregado completo. Los valores
se construyen posicionalmente y no se permite la inicialización dentro de la
declaración:

```bg
active: Permissions = {1, 1, 0}
```
