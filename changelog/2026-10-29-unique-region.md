# Contratos `unique` y metadata `Region_t`

Se añadió un contrato optativo de exclusividad para parámetros de arrays y
`buffer`:

```bg
func process(data: unique int32[], length: Len_t, size: Size_t, region: Region_t) void:
    return
```

`Region_t` es una expansión inmutable suministrada por el compilador y no forma
parte de la llamada fuente. El análisis conserva el aliasing normal para
parámetros sin `unique`, propaga la procedencia de parámetros `unique` y
rechaza regiones repetidas o desconocidas. Los arrays probados como exclusivos
reciben `noalias` en LLVM; los buffers mantienen su descriptor por valor y solo
reciben la validación semántica en esta fase.
