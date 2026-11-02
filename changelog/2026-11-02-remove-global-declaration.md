# Eliminación de la declaración `global`

Las funciones ya no necesitan declarar qué variables de módulo usan:

```bg
counter: int32 = 0

func next() int32:
    counter += 1
    return counter
```

Los globals públicos importados siguen la misma regla, tanto con alias
selectivo como mediante namespace cualificado. Los nombres `private` continúan
protegidos entre módulos. La palabra clave y el nodo sintáctico `global` se
eliminaron; no hay estado adicional ni instrucción LLVM asociada.
