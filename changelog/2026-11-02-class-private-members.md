# Miembros privados de clases

Los atributos y métodos de una `class` cuyo nombre empieza por `_` son
privados. Solo pueden resolverse desde métodos de la misma clase que los
declara; una subclase tampoco puede acceder directamente a los privados
heredados.

```bg
class Account:
    func __init__(value: int32) void:
        self._balance = value

    func _read() int32:
        return self._balance
```

El acceso desde otra clase, una función libre o mediante una referencia de
subclase produce un error semántico. Los nombres sin `_` conservan la
visibilidad pública existente y los hooks mágicos siguen siendo invocados por
el compilador mediante sus rutas internas.

La comprobación se realiza en `core/frontend/tools/types/calls.py` y
`core/frontend/tools/types/values.py`. `FieldSpec` conserva la clase que
declara cada atributo para aplicar la regla también tras aplanar la herencia.
