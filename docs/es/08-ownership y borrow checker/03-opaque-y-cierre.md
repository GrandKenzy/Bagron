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
la llamada. Las funciones con convención `close_*` consumen un descriptor
`owned` y lo marcan como `closed`; un segundo cierre se diagnostica
estáticamente. En este ejemplo, `GetStdHandle` representa la adquisición y
`CloseHandle` la operación nativa real.

Estos estados no se almacenan en el valor LLVM. El descriptor conserva solo su
representación ABI (`void*` o escalar) y el ownership se comprueba durante el
análisis semántico.
