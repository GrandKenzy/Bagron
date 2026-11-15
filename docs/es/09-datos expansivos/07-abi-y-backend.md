# 07. ABI y backend

La firma fuente contiene únicamente los parámetros que el usuario declaró.
El backend puede añadir metadata privada cuando una función necesita leer un
`.<len>` dinámico, por ejemplo en un array abierto o en un `chain` no constante.

Los arrays de tamaño fijo no reciben longitud oculta. `.<size>` se materializa
con el layout ABI del tipo y `.<region>` no ocupa ningún argumento LLVM.
`buffer[]` conserva su descriptor, que contiene sus propios datos y longitud.

La firma visible de una función sigue siendo estable para quien la llama:

```bg
func process(data: uint16[4]) usize:
    return data.<len> * data.<size>
```

Las librerías compiladas guardan la versión de este contrato. Un artefacto
producido con el formato anterior debe reconstruirse antes de enlazarse.
