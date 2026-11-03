# 05. `@frozen` y destrucción

`@frozen` limita la escritura de atributos al inicializador de la clase:

```bg
@frozen
class Config:
    func __init__(port: int32) void:
        self.port = port

    func set_port(port: int32) void:
        self.port = port  # error: la instancia ya está congelada
```

La misma regla se aplica a `__frontend__` cuando esa es la construcción de la
clase. El estado `frozen` debe ser coherente entre una clase y su herencia; no
uses una subclase para reabrir escrituras que el padre cerró.

`Del instance` activa el ciclo de destrucción de una instancia. Si existe
`__deletion__`, ese método se ejecuta como hook de limpieza:

```bg
class FileHandle:
    func __init__(handle: uint64) void:
        self.handle = handle

    func __deletion__() void:
        self.handle = 0

func close_one(file: FileHandle) void:
    Del file
```

Sin `__deletion__` no se inventa una liberación automática. Declara la
limpieza explícitamente cuando el objeto represente un recurso externo.
