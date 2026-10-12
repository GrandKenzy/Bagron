# EGLLibs y `egl pack`

`EGLLibs/` es el destino final de EGL donde se guardan las librerías. Reemplaza a `source/targets/<backend>/` y a `core/backend/<backend>/{externs,libraries}`.

```
EGLLibs/
├── libraries/            # solo .lib.egl que no requieren un backend específico
├── backends/
│   └── c/
│       ├── externs/      # externs específicos de C (.externs.egl)
│       ├── includes/     # carpetas con cabeceras .h (ej. SDL3/SDL.h)
│       ├── libraries/    # .lib.egl específicos del backend C
│       ├── bin/          # binarios (.dll, .so, .dylib)
│       └── lib/          # libSDL3.dll.a, cmake/, pkgconfig/ ...
├── .cache/               # caché (componentes extraídos de .lib.egl)
└── .temp/                # temporales
```

La ubicación se resuelve como `<raíz de EGL>/EGLLibs` o con la variable de entorno `EGL_LIBS`. Las rutas se definen en `core/packages/layout.py`.

## Separación de archivos

| Carpeta | Contenido |
|---|---|
| `libraries/` | **solo** `.lib.egl` |
| `modules/` | **solo** `.egl` (código fuente) |

Los módulos propios del compilador (`standard.egl`, `os.egl`) viven en `core/backend/<backend>/modules/`.

## Resolución de `import`

1. Proyecto: `source/modules/<n>.egl`, `source/<n>.egl`, `libraries/<n>.lib.egl`
2. `EGLLibs/backends/<backend>/libraries/<n>.lib.egl`
3. `EGLLibs/libraries/<n>.lib.egl`
4. Módulos del backend: `core/backend/<backend>/modules/<n>.egl`

## Comandos

```
egl pack install [ruta] [--tar "egl-c"] [-y]
egl pack uninstall [--tar "egl-c"] <Nombre>
egl pack list [--tar "egl-c"]
```

* `pack install` empaqueta el proyecto como `.lib.egl` usando el **nombre de la carpeta**. Sin `--tar` se instala en `EGLLibs/libraries`; con `--tar "egl-c"`, en `EGLLibs/backends/c/libraries`.
* Si ya existe una librería con ese nombre avisa y pregunta si se reemplaza (`-y`/`--force` omite la pregunta; sin terminal interactiva se cancela).
* `pack uninstall` elimina la librería y su caché extraída.

## Un `.lib.egl` contiene todo

Al empaquetar se incluyen, si existen en la raíz del proyecto (o en `source/`), las carpetas `externs/`, `includes/`, `lib/` y `bin/`, guardadas dentro del zip como `backend/<backend>/<tipo>/...`. Así una librería como SDL3 viaja completa (externs, cabeceras, `libSDL3.dll.a`, `SDL3.dll`).

Al importarla, el compilador extrae esos componentes a `EGLLibs/.cache/libs/<backend>/<nombre>/` y registra automáticamente los `-I`, `-L`, las DLL a desplegar y los externs disponibles para `include`.

## Propagación de `clause Target`

* El `Target` de `main.egl` se propaga a todo lo que se importe.
* Un módulo (`.egl`) puede declarar su propia `clause Target`; si la omite, usa el de `main.egl`. Si declara uno distinto, el compilador lanza `TargetMismatchError`. Aplica también a imports transitivos.
* Todo `.lib.egl` guarda su `target` en `manifest.json`. Si no coincide con el de `main.egl`, o falta, es un error.
* Con `egl pack install --tar "egl-c"` el `target` queda fijado a ese valor; sin `--tar` se usa el `Target` del `main.egl` de la librería.
* La comparación ignora comillas, mayúsculas y el prefijo `egl-` (`"EGL-C"`, `'egl-c'` y `c` son equivalentes).
