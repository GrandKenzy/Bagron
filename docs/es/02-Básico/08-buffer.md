# `buffer`

`buffer` representa un descriptor de memoria dinámica compuesto por bytes. La
capacidad se fija en el tipo y la memoria se libera explícitamente con `Del`.

```bg
data: buffer[4] = {10, 20, 30, 40}
data[0] = 65
Del data
```

`buffer[N]` y `byte[N]` no son aliases: el primero posee una reserva dinámica
y el segundo es un array ordinario. `buffer[]` puede inferir su capacidad al
inicializarse desde una concatenación.

## `.<len>`

Un parámetro de buffer recibe el descriptor completo y consulta su longitud
sin declarar metadata adicional:

```bg
func fill(data: buffer[]) usize:
    if data.<len> > 0:
        data[0] = 1
    return data.<len>
```

`.<size>` no aplica a `buffer`; sus unidades ya son bytes. Un `buffer` tampoco
se convierte silenciosamente en `byte[]`, `char[]`, `chain` ni puntero crudo.

## Ownership

Una variable local de buffer es `owned` y puede ejecutar `Del` una vez. Un
parámetro ordinario es `borrowed`: puede leerse y modificarse, pero no puede
liberarse. Después de `Del`, el binding queda `dead` y cualquier uso posterior
se diagnostica. Las ramas se fusionan conservadoramente.

Los valores de buffer se mueven al inicializar o asignar otro destino
compatible; copiar sobre un destino que ya posee un recurso se rechaza. Los
arrays o structs que contienen recursos siguen la misma regla por campo.

`unique` añade un préstamo exclusivo sin usar un parámetro de región:

```bg
func clear(data: unique buffer[]) void:
    if data.<len> > 0:
        data[0] = 0
```

Dos préstamos que puedan referirse a la misma región se rechazan. Los campos
distintos de un agregado pueden prestarse por separado, pero el agregado
completo se solapa con cualquiera de sus campos.
