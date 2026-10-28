# Integracion De Librerias Compiladas (Caso SDL3)

> **Estado:** el backend activo ya procesa `include "header" link "library"`
> para resolver headers nativos y pasar bibliotecas al enlace LLVM. Los
> contratos `.externs.egl` y la generación de `program.c` siguen fuera del
> frontend canónico actual.

Este documento detalla la arquitectura de integracion de librerias nativas en **Bagron** (o **Bagron**), utilizando la biblioteca multimedia **SDL3** como caso de estudio practico.

---

## Arquitectura De Integracion

El enlace de una biblioteca nativa en Bagron desacopla el binario del lenguaje mediante capas especificas:

```
[ Binario Nativo C/C++: SDL3.dll, libSDL3.a ]
                     ^
                     | Directivas de enlace (@link, @bin, @header)
[ Contrato Externs: source/targets/c/extends/sdl3.externs.egl ]
                     ^
                     | Importacion con alias (import sdl3 as C_SDL3)
[ Modulo Idiomatico Bagron: source/targets/c/libraries/sdl3.egl ]
                     ^
                     | Importacion y consumo (import sdl3)
[ Codigo De Aplicacion: source/main.egl ]
```

---

## Directivas Nativas

Las dependencias nativas se declaran directamente en Bagron:

```bg
include "windows" link "kernel32"
```

Bagron agrega `.h` al nombre del header y resuelve la biblioteca nativa para el
enlace del target. El header se valida con el preprocesador de `clang`, pero no
se copia ni se interpreta como código Bagron.

El diseño histórico de contratos conserva estas directivas como referencia:

| Directiva | Argumento | Funcion |
| :--- | :--- | :--- |
| `@header` | `<cabecera.h>` | Genera la instruccion `#include <cabecera.h>` en `program.c`. |
| `@link` | `<nombre>` | Agrega la bandera `-l<nombre>` al invocar el compilador nativo (ej. `-lSDL3`). |
| `@bin` | `<archivo>` | Declara el binario dinamico en ejecucion (`.dll`, `.so`). |
| `@lib_dir` | `<directorio>` | Agrega una ruta de busqueda de librerias (`-L <dir>`). |
| `@include_dir` | `<directorio>` | Agrega una ruta de busqueda de cabeceras (`-I <dir>`). |

---

## Declaracion Del Contrato Externo (`sdl3.externs.egl`)

Se define en `source/targets/c/extends/sdl3.externs.egl` para ensenar al analizador semantico las firmas exactas de la libreria:

```egl
; Firmas de Simple DirectMedia Layer 3 (SDL3) para Bagron
@header SDL3/SDL.h
@link SDL3
@bin SDL3.dll

; Ciclo de Vida
bool SDL_Init(uint flags)
void SDL_Quit()
pstring SDL_GetError()

; Ventanas
ptr SDL_CreateWindow(pstring title, int w, int h, uint64 flags)
void SDL_DestroyWindow(ptr window)

; Renderizado 2D
ptr SDL_CreateRenderer(ptr window, pstring name)
void SDL_DestroyRenderer(ptr renderer)
bool SDL_SetRenderDrawColor(ptr renderer, uint8 r, uint8 g, uint8 b, uint8 a)
bool SDL_RenderClear(ptr renderer)
bool SDL_RenderFillRect(ptr renderer, ptr rect)
bool SDL_RenderPresent(ptr renderer)

; Eventos y Entrada
bool SDL_PollEvent(ptr event)
void SDL_Delay(uint32 ms)
```

En las firmas de contratos:
- `ptr`: representa un puntero generico `void*`.
- `pstring`: representa una cadena de caracteres `char*`.
- Tipos basicos (`bool`, `uint`, `uint32`, `int`, `float`) mapean a tipos de maquina de `standard.egl`.

---

## Modulo Idiomatico En Bagron (`sdl3.egl`)

Construye una capa orientada a objetos en `source/targets/c/libraries/sdl3.egl` sobre el contrato en C:

```egl
import sdl3 as C_SDL3
import standard

; Estructuras planas compatibles con memoria C
struct Rect:
    int x
    int y
    int w
    int h

struct FRect:
    float x
    float y
    float w
    float h

struct Event:
    uint32 type
    uint32 _p1
    uint64 _p2
    uint64 _p3
    uint64 _p4
    uint64 _p5
    uint64 _p6
    uint64 _p7
    uint64 _p8
    uint64 _p9
    uint64 _p10
    uint64 _p11
    uint64 _p12
    uint64 _p13
    uint64 _p14
    uint64 _p15
    uint64 _p16

; Enumeraciones tipadas
enum EventType:
    QUIT = 256

; Clases con ciclo de vida RAII
class Window:
    ptr _handle
    ptr _renderer

    void __init__(pstring title, int width = 640, int height = 480):
        self._handle = C_SDL3.SDL_CreateWindow(title, width, height, 0)
        self._renderer = C_SDL3.SDL_CreateRenderer(self._handle, Null)

    @method
    void destroy():
        C_SDL3.SDL_DestroyRenderer(self._renderer)
        C_SDL3.SDL_DestroyWindow(self._handle)

; Funciones en linea que resuelven directo al binario C
__inline__ bool init(uint flags): return C_SDL3.SDL_Init(flags)
__inline__ void quit(): C_SDL3.SDL_Quit()
__inline__ bool poll_event(ptr event): return C_SDL3.SDL_PollEvent(event)
__inline__ bool set_draw_color(ptr renderer, uint8 r, uint8 g, uint8 b, uint8 a): return C_SDL3.SDL_SetRenderDrawColor(renderer, r, g, b, a)
__inline__ bool clear(ptr renderer): return C_SDL3.SDL_RenderClear(renderer)
__inline__ bool fill_rect(ptr renderer, ptr rect): return C_SDL3.SDL_RenderFillRect(renderer, rect)
__inline__ bool present(ptr renderer): return C_SDL3.SDL_RenderPresent(renderer)
__inline__ void delay(uint32 ms): C_SDL3.SDL_Delay(ms)
```

---

## Consumo En El Archivo Principal (`main.egl`)

El desarrollador consume la libreria mediante sintaxis limpia sin tocar cabeceras de C manualmente:

```egl
clause Target 'egl-c'

import sdl3
import standard

declare sdl3.Window as Window
declare sdl3.Event as Event
declare sdl3.FRect as FRect
declare sdl3.EventType as EventType

sdl3.init(0)

Window ventana = Window("Bagron SDL3 - Demo", 640, 480)
FRect rect = FRect(220.0, 165.0, 200.0, 150.0)

bool running = true
Event event

while running:
    while sdl3.poll_event(&event):
        if event.type == EventType.QUIT:
            running = false

    sdl3.set_draw_color(ventana._renderer, 30, 30, 45, 255)
    sdl3.clear(ventana._renderer)
    sdl3.set_draw_color(ventana._renderer, 80, 180, 240, 255)
    sdl3.fill_rect(ventana._renderer, &rect)
    sdl3.present(ventana._renderer)
    sdl3.delay(16)

ventana.destroy()
sdl3.quit()
```

---

## Compilacion Y Enlace Con El CLI

Para compilar y enlazar el proyecto con la libreria nativa:

```bash
# Compilar a C y generar binario nativo con GCC:
egl compile source --build

# Compilar, construir y ejecutar en un solo paso:
egl run source
```

El analizador detecta las directivas `@link SDL3` y `@bin SDL3.dll` de forma automatica, inyectando `-lSDL3` en la llamada a GCC y resolviendo las cabeceras correspondientes en `program.c`.

Si las librerias se encuentran en ubicaciones personalizadas del sistema, se pasan banderas adicionales por consola:
```bash
egl compile source --build -I "C:/libs/SDL3/include" -L "C:/libs/SDL3/lib" -l SDL3
```
