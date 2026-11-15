# 05. Alcance real del borrow checker

Bagron tiene comprobaciones de ownership y préstamos, pero no un borrow
checker general con el modelo completo de Rust. El nombre describe una
familia de comprobaciones estáticas; no implica que Bagron verifique toda la
vida de cualquier puntero o alias. Actualmente las reglas se concentran en:

- estados `owned`, `borrowed`, `dead` y `closed` de `buffer` y `opaque`;
- consumo explícito con `Del` y funciones `@consume` (o la convención `close_*`);
- transferencia de propiedad de descriptores `opaque` al copiarlos, asignarlos o retornarlos;
- detección de fugas al salir de ámbito o en retornos tempranos (advertencia por defecto y error con `--strict-ownership`);
- exclusividad demostrable de parámetros `unique` mediante procedencia de lugares;
- procedencia y seguridad de punteros en la frontera `@unsafe`.

El comprobador sí puede rechazar usos después de `Del`, movimientos repetidos,
cierres repetidos, fugas en rutas conocidas y alias incompatibles con
`unique`. No puede validar la dirección real de un puntero crudo, observar
modificaciones hechas por FFI o por el sistema operativo, inferir la vida de
una dirección exportada con `$`, ni garantizar que una clase o recurso externo
se cierre correctamente si su API no declara ese contrato.

`--strict-ownership` convierte las fugas diagnosticables al salir de ámbito o
por retorno en errores. No convierte `@unsafe` en seguro ni añade análisis
dinámico: un programa puede compilar en modo estricto y aun así violar el
contrato de un puntero crudo si el código inseguro mintió sobre su dirección,
longitud o vida.

Por ejemplo, pasar un `buffer` a una función ordinaria no transfiere su
ownership:

```bg
func inspect(data: buffer[]) void:
    return

func use(data: buffer[4]) void:
    inspect(data)
    data[0] = 1
```

El llamador conserva el buffer. No dependas de estas reglas para hacer seguro
un puntero crudo: los punteros pueden aliasar y no llevan longitud. Para esos
casos usa una frontera `@unsafe` y documenta la garantía que debe cumplir el
llamador.

## Contratos inferidos en las llamadas

Bagron completa automáticamente los parámetros ocultos cuando la llamada
aporta una procedencia demostrable. La inferencia no inventa longitudes ni
regiones: si el compilador no puede demostrar el contrato, la llamada se
rechaza y debe corregirse la firma o el origen del argumento.

### Miembros de compilador

`.<len>` y `.<size>` se leen desde el valor fuente y se propagan por las
llamadas cuando el ABI lo necesita. `.<region>` solo consulta procedencia
simbólica; no se declara, almacena ni pasa como argumento.

Dos parámetros `unique` no pueden recibir la misma región, y ningún préstamo
ordinario puede compartir la región mientras exista el préstamo exclusivo.

Los temporales, punteros crudos, globals y expresiones cuya procedencia no se
puede identificar no satisfacen este contrato automáticamente. La solución es
pasar el binding local correcto, propagar un parámetro `unique` o eliminar la
exclusividad si la operación solo necesita un préstamo ordinario.
