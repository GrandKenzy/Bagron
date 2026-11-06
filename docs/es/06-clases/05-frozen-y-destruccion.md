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

`Del instance` activa el ciclo de destrucción de una instancia y limpia
automáticamente a cero todos sus bytes de memoria.

Por defecto, la limpieza automática se produce **antes** de ejecutar
`__deletion__` (de modo que el hook recibe la instancia con su memoria ya
limpia). Si se necesita inspeccionar o liberar recursos externos usando los
valores originales de los campos antes de la limpieza, se decora `__deletion__`
con `@before`:

```bg
class FileHandle:
    func __init__(handle: uint64) void:
        self.handle = handle

    @before
    func __deletion__() void:
        ; Se ejecuta antes de que la memoria se limpie a cero
        if self.handle != 0:
            self.handle = 0

func close_one(file: FileHandle) void:
    Del file
```

Si la clase no define `__deletion__`, `Del instance` pone a cero los bytes de la
instancia automáticamente sin requerir un método explícito.
