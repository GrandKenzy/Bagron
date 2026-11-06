# 05. Alcance real del borrow checker

Bagron tiene comprobaciones de ownership y préstamos, pero no un borrow
checker general con el modelo completo de Rust. Actualmente las reglas se
concentran en:

- estados `owned`, `borrowed`, `dead` y `closed` de `buffer` y `opaque`;
- consumo explícito con `Del` y funciones `@consume` (o la convención `close_*`);
- transferencia de propiedad de descriptores `opaque` al copiarlos, asignarlos o retornarlos;
- detección de fugas al salir de ámbito o en retornos tempranos (advertencia por defecto y error con `--strict-ownership`);
- exclusividad demostrable de parámetros `unique` mediante `Region_t`;
- procedencia y seguridad de punteros en la frontera `@unsafe`.

Por ejemplo, pasar un `buffer` a una función ordinaria no transfiere su
ownership:

```bg
func inspect(data: buffer[], length: Len_t) void:
    return

func use(data: buffer[4]) void:
    inspect(data, 4)
    data[0] = 1
```

El llamador conserva el buffer. No dependas de estas reglas para hacer seguro
un puntero crudo: los punteros pueden aliasar y no llevan longitud. Para esos
casos usa una frontera `@unsafe` y documenta la garantía que debe cumplir el
llamador.
