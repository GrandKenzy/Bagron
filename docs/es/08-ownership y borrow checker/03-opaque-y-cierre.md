# 03. Descriptores `opaque`

Los descriptores `opaque` también tienen estado estático:

```bg
clause System 'windows'

opaque HANDLE: void*

extern windows "kernel32":
    GetStdHandle(kind: uint32) HANDLE
    CloseHandle(handle: HANDLE) int32

func close_handle(handle: HANDLE) void:
    status: int32 = CloseHandle(handle)
    return

func release_one() void:
    handle: HANDLE = GetStdHandle(0)
    close_handle(handle)
    return
```

Los retornos y las variables locales empiezan como `owned`; los parámetros
ordinarios son `borrowed`. Las llamadas normales prestan el descriptor durante
la llamada. Una función marcada con `@consume` consume un descriptor `owned` y
lo marca como `closed`; un segundo cierre se diagnostica estáticamente. En este
ejemplo, `GetStdHandle` representa la adquisición y `CloseHandle` la operación
nativa real:

```bg
@consume
func close_handle(handle: HANDLE) void:
    status: int32 = CloseHandle(handle)
    return
```

Dentro de una función `@consume`, sus parámetros `opaque` son `owned` y pueden
cerrarse o reenviarse a otra función `@consume`. `@consume` exige al menos un
parámetro `opaque`.

> La convención por prefijo `close_*` sigue funcionando por compatibilidad (y es
> la única disponible para `extern`, que no admite decoradores), pero una
> función Bagron que la usa sin `@consume` emite una advertencia.

### Copia y asignación

Un descriptor es un handle único: copiarlo mueve su propiedad. Tras
`g: FD = h` o `g = h`, `g` es `owned` y `h` pasa a `moved`; usar `h` después se
diagnostica. Solo se puede mover un descriptor `owned` local: un parámetro
`borrowed` o un global no pueden transferirse.

### Bucles

Cerrar o mover dentro de un bucle un descriptor declarado fuera de él se
rechaza, porque una segunda iteración lo usaría tras consumirlo. Un descriptor
declarado dentro del cuerpo del bucle sí puede consumirse en esa iteración.

Estos estados no se almacenan en el valor LLVM. El descriptor conserva solo su
representación ABI (`void*` o escalar) y el ownership se comprueba durante el
análisis semántico.
