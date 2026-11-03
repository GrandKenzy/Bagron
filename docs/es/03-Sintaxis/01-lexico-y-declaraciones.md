# Léxico y declaraciones

## Líneas, comentarios e indentación

Los archivos `.bg` usan saltos de línea e indentación para delimitar bloques.
El comentario empieza con `;` y termina en la línea actual:

```bg
; El comentario no llega al parser semántico.
value: int32 = 4
```

No se escriben `;` al final de una sentencia. La indentación debe ser
consistente dentro de una función, clase o declaración agregada.

## Variables y constantes

El nombre precede al tipo. Los escalares locales necesitan inicializador; los
arrays y agregados pueden recibir almacenamiento determinista sin uno:

```bg
count: int32 = 0
limit: const int32 = 10
values: int32[3] = {1, 2, 3}
```

`const` se escribe delante del tipo y protege el valor o todos los elementos
del array. `chain` ya es inmutable y no admite `const chain`.

## Funciones

```bg
func add(left: int32, right: int32) int32:
    return left + right

func clear() void:
    return
```

El retorno forma parte de la firma. `main` debe ser global y devolver `int32`;
una función `void` usa `return` vacío.

## Visibilidad y especificadores

Las declaraciones son públicas por defecto. `private` limita el uso al módulo;
`public` hace explícita la exportación:

```bg
private func helper() int32:
    return 1

public func answer() int32:
    return helper()
```

`inline` es un especificador de función, no un decorador con `@`.
