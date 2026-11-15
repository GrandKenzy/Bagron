# 06. `unique` y procedencia

`unique` describe un préstamo exclusivo en la llamada; no requiere un
parámetro `Region_t`:

```bg
func normalize(values: unique int32[]) void:
    if values.<len> > 0:
        values[0] = 0

func main() int32:
    values: int32[2] = {4, 8}
    normalize(values)
    return 0
```

El compilador comprueba que dos préstamos `unique` no se solapen. Los campos
distintos de un struct pueden prestarse por separado; el struct completo y un
campo suyo sí se solapan. Los arrays se consideran solapados cuando el índice
no puede demostrarse como una región distinta.

`.<region>` solo permite consultar procedencia conocida durante el análisis.
Es metadata simbólica: no se almacena, no se retorna y no se pasa como un
argumento ordinario.
