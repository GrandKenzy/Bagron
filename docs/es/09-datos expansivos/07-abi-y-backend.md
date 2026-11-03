# 07. ABI y backend

Los parámetros expansivos forman parte de la firma ABI aunque la llamada
fuente sea corta. En LLVM ocurre lo siguiente:

- `Len_t`, `Size_t` y `Signed_t` se emiten como argumentos enteros de tamaño
  de puntero;
- `Region_t` se conserva solo como metadata semántica y no ocupa un argumento
  LLVM de runtime;
- `unique` array puede recibir `noalias` cuando la prueba de exclusividad es
  válida;
- `unique buffer[]` conserva el descriptor por valor y no recibe `noalias`
  sobre su puntero interno.

Por eso una función que se exporta o se consume desde una librería debe
conservar exactamente la misma firma expansiva. Cambiar el orden de los
metadatos altera el contrato aunque las llamadas visibles parezcan iguales.

```bg
func process(
    data: uint16[4],
    length: Len_t,
    element_size: Size_t,
    signed: Signed_t
) void:
    return
```

La representación final es responsabilidad del backend; el código fuente
solo declara qué metadatos necesita el cuerpo y en qué relación están con el
dato principal.
