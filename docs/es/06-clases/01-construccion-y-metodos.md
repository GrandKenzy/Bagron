# 01. Construcción y métodos

Una clase agrupa campos y métodos con layout conocido en compilación. Una
clase construible declara exactamente un iniciador `__init__`:

```bg
class Point:
    func __init__(x: int32, y: int32) void:
        self.x = x
        self.y = y

    func total() int32:
        return self.x + self.y

func main() int32:
    point: Point = Point(2, 3)
    return point.total()
```

`self` es implícito en la firma de los métodos de instancia. Los campos se
crean al asignarlos desde el iniciador y se acceden con `self.campo`. Una clase
sin `__init__` no se puede construir con `Clase(...)`.

`__frontend__` es la alternativa para clases que deben aceptar una conversión
producida por el frontend:

```bg
class Greeting:
    __frontend__(text: Text) void:
        self.text = text
```

Elige una sola estrategia de construcción por clase: no mezcles varios
iniciadores esperando sobrecarga automática.
