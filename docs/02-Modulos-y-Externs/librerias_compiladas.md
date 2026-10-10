# Integracion de Librerias Compiladas Nativas (Caso de Estudio: SDL3)

Easy-C (EGL) cuenta con un sistema de enlace foraneo y metaprogramacion disenado para consumir cualquier libreria compilada en C/C++ (archivos `.dll`, `.so`, `.dylib`, `.lib` o `.a`) sin necesidad de escribir wrappers manuales en C ni alterar el compilador.

Este documento explica paso a paso la arquitectura completa para anadir e integrar una libreria externa compilada, utilizando la implementacion real de **SDL3** en Easy-C como ejemplo guiado.

---

## 1. Arquitectura de Integracion

La integracion de una libreria nativa consta de 3 capas claramente desacopladas:

```
[Binario C/C++ (SDL3.dll, libSDL3.a)]
                ▲
                │ Enlace en tiempo de compilacion (@link, @bin, @header)
[1. Contrato Externs: source/targets/c/extends/sdl3.externs.egl]
                ▲
                │ Importacion e inclusion con alias (include "sdl3" as C_SDL3)
[2. Modulo Idiomatico EGL: source/targets/c/libraries/sdl3.egl]
                ▲
                │ Consumo del desarrollador (import sdl3, declare ...)
[3. Codigo de Aplicacion: source/main.egl]
```

### Jerarquia de Archivos en el Proyecto:

```text
mi_proyecto/
├── source/
│   ├── main.egl                        <-- Codigo de la aplicacion
│   └── targets/
│       └── c/                          <-- Backend activo (egl-c)
│           ├── extends/
│           │   └── sdl3.externs.egl    <-- Capa 1: Firmas C + directivas del linker
│           └── libraries/
│               └── sdl3.egl            <-- Capa 2: Abstraccion orientada a objetos en EGL
```

---

## 2. Paso 1: Declarar el Contrato Externo (`sdl3.externs.egl`)

El archivo `.externs.egl` se coloca en `source/targets/<backend>/extends/<nombre>.externs.egl`. Su proposito es ensenar al analizador semantico las firmas exactas de la libreria C y configurar automaticamente las banderas del compilador nativo (GCC).

### Directivas de Metadatos (`@`)

Al inicio del archivo se configuran las dependencias nativas:

| Directiva | Argumento | Efecto en la Compilacion |
| :--- | :--- | :--- |
| `@header` | `<ruta/cabecera.h>` | Genera `#include <ruta/cabecera.h>` en el archivo C monolitico. |
| `@link` | `<nombre>` | Agrega la bandera `-l<nombre>` al enlazar con GCC (ej. `@link SDL3` -> `-lSDL3`). |
| `@bin` | `<archivo>` | Indica la biblioteca dinamica en tiempo de ejecucion (ej. `SDL3.dll`). El CLI la copia automaticamente al directorio de salida. |
| `@lib_dir` | `<directorio>` | Agrega una ruta de busqueda de librerias al linker (`-L <dir>`). |
| `@include_dir` | `<directorio>` | Agrega una ruta de busqueda de cabeceras C (`-I <dir>`). |

### Ejemplo: `source/targets/c/extends/sdl3.externs.egl`

```easy-c
; ==============================================================================
; Firmas de Simple DirectMedia Layer 3 (SDL3) para Easy-C
; ==============================================================================
@header SDL3/SDL.h
@link SDL3
@bin SDL3.dll

; --- Ciclo de Vida ---
bool SDL_Init(uint flags)
void SDL_Quit()
pstring SDL_GetError()

; --- Ventanas ---
ptr SDL_CreateWindow(pstring title, int w, int h, uint64 flags)
void SDL_DestroyWindow(ptr window)

; --- Renderizado 2D ---
ptr SDL_CreateRenderer(ptr window, pstring name)
void SDL_DestroyRenderer(ptr renderer)
bool SDL_SetRenderDrawColor(ptr renderer, uint8 r, uint8 g, uint8 b, uint8 a)
bool SDL_RenderClear(ptr renderer)
bool SDL_RenderFillRect(ptr renderer, ptr rect)
bool SDL_RenderPresent(ptr renderer)

; --- Eventos y Entrada ---
bool SDL_PollEvent(ptr event)
void SDL_Delay(uint32 ms)
```

> [!NOTE]
> En las firmas de `.externs.egl`:
> * `ptr` representa un puntero generico `void*`.
> * `pstring` representa un puntero de cadena de C `char*`.
> * Los tipos de datos basicos son los definidos en `standard.egl` (`bool`, `uint`, `uint32`, `int`, `float`, etc.).

---

## 3. Paso 2: Crear el Modulo Idiomatico en EGL (`sdl3.egl`)

En lugar de forzar a los desarrolladores a llamar a las funciones crudas de C (`SDL_CreateWindow`, `SDL_DestroyWindow`), se define una libreria de target en `source/targets/c/libraries/sdl3.egl`.

Esta capa utiliza `include` con alias para acceder al contrato C y construye una interfaz moderna con clases, estructuras y enums:

```easy-c
include "sdl3" as C_SDL3
import standard

; 1. Estructuras compatibles con C (Layout directo)
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

; 2. Enums fuertemente tipados
enum EventType:
    QUIT = 256

; 3. Clases con gestion de ciclo de vida (RAII)
class Window:
    ptr _handle
    ptr _renderer

    void __init__(self, pstring title, int width = 640, int height = 480):
        self._handle = C_SDL3.SDL_CreateWindow(title, width, height, 0)
        self._renderer = C_SDL3.SDL_CreateRenderer(self._handle, Null)

    @method
    void destroy(self):
        C_SDL3.SDL_DestroyRenderer(self._renderer)
        C_SDL3.SDL_DestroyWindow(self._handle)

; 4. Funciones en linea que mapean al backend nativo
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

## 4. Paso 3: Consumir la Libreria en `main.egl`

En el punto de entrada de la aplicacion (`source/main.egl`), se importa el modulo y se declaran los simbolos necesarios:

```easy-c
clause Target 'egl-c'

import sdl3
import standard

declare sdl3.Window as Window
declare sdl3.Event as Event
declare sdl3.FRect as FRect
declare sdl3.EventType as EventType

; Inicializacion del subsistema
sdl3.init(0)

; Creacion de recursos mediante constructores de EGL
Window ventana = Window("Easy-C SDL3 - Rectangulo y Eventos", 640, 480)
FRect rect = FRect(220.0, 165.0, 200.0, 150.0)

bool running = true
Event event

; Bucle principal de eventos y renderizado
while running:
    while sdl3.poll_event(&event):
        if event.type == EventType.QUIT:
            running = false

    ; Dibujo en pantalla
    sdl3.set_draw_color(ventana._renderer, 30, 30, 45, 255)
    sdl3.clear(ventana._renderer)
    sdl3.set_draw_color(ventana._renderer, 80, 180, 240, 255)
    sdl3.fill_rect(ventana._renderer, &rect)
    sdl3.present(ventana._renderer)
    sdl3.delay(16)

; Liberacion de recursos
ventana.destroy()
sdl3.quit()
```

---

## 5. Paso 4: Compilacion y Enlace con el CLI

Al compilar el proyecto con `--build` o `--run`, Easy-C lee automaticamente las directivas declaradas en el contrato:

```bash
# Compilar y construir el binario ejecutable:
python egl.py compile source --build

# O compilar y ejecutar inmediatamente:
python egl.py run source
```

### Proceso Interno de Enlace:

1. **Deteccion Automatica:** El analizador encuentra `@link SDL3` y `@bin SDL3.dll` en `sdl3.externs.egl`.
2. **Generacion de C:** Genera `program.c` incluyendo `#include <SDL3/SDL.h>` y las llamadas a las funciones foraneas.
3. **Invocacion de GCC:** Invoca el compilador C pasando la bandera `-lSDL3` automaticamente:
   ```bash
   gcc program.c -o program.exe -lSDL3
   ```
4. **Despliegue de Binarios:** Si `SDL3.dll` esta presente en el entorno o en las rutas del proyecto, queda enlazada y lista para la ejecucion del programa.

### Opciones Manuales por Consola (Opcionales)

Si las cabeceras o librerias binarias se encuentran en rutas no estandar del sistema, se pueden anadir opciones adicionales directamente en el CLI:

```bash
python egl.py compile source --build -I "C:/libs/SDL3/include" -L "C:/libs/SDL3/lib" -l SDL3
```
