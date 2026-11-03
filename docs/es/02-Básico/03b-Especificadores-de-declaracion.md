# Especificadores de declaración y almacenamiento

## `public` y `private`

Controlan la visibilidad de una declaración en su módulo o clase:

```bg
public answer: int32 = 42
private counter: int32 = 0

public func read_answer() int32:
    return answer
```

Si no se escribe ninguno, la declaración es pública por defecto. Se admiten
en variables, funciones, `struct`, `mold`, `flags`, `enum`, `class` y
`opaque`. Un miembro privado de una clase solo es accesible desde la clase que
lo declara; una subclase no hereda ese acceso.

La palabra `global` ya no existe como declaración. Las funciones resuelven los
globals públicos visibles, pero la privacidad se comprueba antes de resolver
el símbolo.

## `inline`

`inline` se escribe antes de `func`, no con `@`:

```bg
inline func add(left: int32, right: int32) int32:
    return left + right
```

En `prod` y `high` Bagron emite `alwaysinline`; en `dev` conserva
`inlinehint`. No cambia la firma, el tipo ni el nivel de seguridad, y no se
aplica a `extern` ni a cuerpos ASM.

## `volatile`

`volatile` califica el agregado completo:

```bg
volatile struct UART:
    status: uint32
    control: uint32
```

También puede usarse con `mold` y `flags`. Conserva las lecturas y escrituras
como accesos volátiles, útil para MMIO o registros externos. No hace las
operaciones atómicas, no añade sincronización y no reemplaza `@unsafe` cuando
la dirección procede de un puntero no demostrable.
