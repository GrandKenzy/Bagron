# 03. Handlers y descriptores `opaque`

Un handler de sistema es un identificador de un recurso que tiene una vida
externa al lenguaje. En Bagron se representa como `opaque` cuando la biblioteca
debe ocultar su layout y controlar cómo se adquiere y se libera. El descriptor
no es el recurso en sí ni una garantía de que el sistema operativo lo acepte:
es el valor ABI que permite transportar esa identidad bajo un contrato de
ownership estático.

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
ordinarios son `borrowed`. Una llamada ordinaria presta el descriptor durante
la llamada y no transfiere su ownership. Una función marcada con `@consume`
recibe la propiedad de sus parámetros `opaque`: el argumento del llamador pasa
a `moved` y el parámetro consumidor debe cerrarlo o transferirlo antes de salir.
Al cerrar un descriptor consumido, su estado queda `closed`; usarlo o cerrarlo
otra vez se diagnostica estáticamente. En este ejemplo, `GetStdHandle`
representa la adquisición y `CloseHandle` la operación nativa real:

```bg
@consume
func close_handle(handle: HANDLE) void:
    status: int32 = CloseHandle(handle)
    return
```

Dentro de una función `@consume`, sus parámetros `opaque` son `owned` y pueden
cerrarse o reenviarse a otra función `@consume`. `@consume` exige al menos un
parámetro `opaque` y solo se admite en funciones, no en métodos.

`@consume` no cierra el recurso por sí solo, no llama automáticamente a una
función nativa y no convierte un `opaque` en un puntero seguro. Solo declara
quién recibe la obligación de cerrar o transferirlo. La implementación debe
realizar explícitamente la operación nativa correspondiente.

> La convención por prefijo `close_*` se conserva para código legacy y para
> funciones `extern`, que no admiten decoradores. En una función Bagron nueva,
> declara `@consume`: si solo se usa el prefijo, el compilador emite una
> advertencia para pedir un contrato explícito.

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
análisis semántico. Por eso el comprobador no puede cerrar un recurso por ti ni
reparar una API nativa que haya usado el handler después de moverlo.
