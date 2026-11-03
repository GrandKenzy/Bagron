# 03. Herencia estática

La herencia es simple y se resuelve en compilación. La subclase debe declarar
su propio iniciador y llamar explícitamente al de la clase base:

```bg
class Point:
    func __init__(x: int32, y: int32) void:
        self.x = x
        self.y = y

class Square(Point):
    func __init__(side: int32) void:
        super.__init__(side, side)
```

Los campos heredados se aplanan en el layout de la subclase. La clase base
debe tener un iniciador compatible con la llamada a `super.__init__`; no hay
dispatch virtual ni tabla de métodos en runtime.

Evita repetir nombres de campos entre padre e hija. La herencia sirve para
reutilizar layout y métodos conocidos, no para crear jerarquías dinámicas.
