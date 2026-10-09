# Sistema Extends: Extension Modular de Librerias

En proyectos de software reales, es habitual requerir funciones adicionales de librerias estandar de C que no vienen precargadas en el compilador base, o adaptar contratos para plataformas especificas. Easy-C (EGL) provee el mecanismo **Extends**, que permite a cualquier proyecto ampliar o personalizar las firmas de librerias nativas de forma local y no destructiva, sin necesidad de modificar el nucleo del compilador.

---

## Especificacion Tecnica

### Ubicacion de Archivos Extends

Los archivos de extension deben ubicarse dentro de la carpeta del proyecto bajo la siguiente jerarquia de directorios:

```
mi_proyecto/
├── main.egl
└── targets/
    └── c/
        └── extends/
            ├── stdio.externs.egl
            └── custom_lib.externs.egl
```

La ruta estandar esperada por el compilador es:
`source/targets/<nombre_backend>/extends/<nombre_libreria>.externs.egl`

Donde `<nombre_backend>` corresponde al identificador limpio del target configurado en la clausula principal (ej. si `clause Target 'egl-c'`, el backend es `c`).

---

## Mecanismo de Fusion (*Merge*) en `ExternsManager`

Cuando el compilador procesa una directiva `include "stdio"`, el metodo `load_include()` en `core/externs/manager.py` ejecuta el siguiente protocolo de resolucion:

```
                    [include "stdio"]
                            │
                            ▼
        ┌───────────────────┴───────────────────┐
        ▼                                       ▼
[Buscar en Backend]                    [Buscar en Extends]
core/backend/c/externs/stdio...        source/targets/c/extends/stdio...
        │                                       │
        ▼ (Si existe)                           ▼ (Si existe)
[Cargar simbolos base]                 [Cargar simbolos de extension]
(fopen, fclose, fread, etc.)           (puts, getchar, etc.)
        │                                       │
        └───────────────────┬───────────────────┘
                            │
                            ▼
             [Fusion: symbols.update(extends)]
                            │
                            ▼
           [Contrato Unificado y Definitivo]
```

### Reglas de Resolucion:

1. **Prioridad No Destructiva:** Los simbolos declarados en el archivo de extension se fusionan con el diccionario de simbolos base mediante `symbols.update(es)`.
2. **Adicion de Nuevas Funciones:** Las funciones que no existian en el backend quedan inmediatamente disponibles para el codigo EGL.
3. **Sobreescritura de Firmas:** Si un simbolo de extension coincide en nombre con un simbolo del backend, la definicion local del proyecto prevalece sobre la del compilador base.
4. **Validacion de Ausencia:** Si la libreria no se encuentra ni en `core/backend/` ni en `source/targets/`, el compilador lanza:
   ```
   RuntimeError: Librería externa 'nombre' no encontrada en backend/c/externs ni extends.
   ```

---

## Ejemplo Practico

### 1. Definicion Base en el Backend
En `core/backend/c/externs/stdio.externs.egl`:
```easy-c
ptr fopen(str filepath, str mode = "rb")
int fclose(ptr stream)
int fseek(ptr stream, int64 offset, int origin)
int64 ftell(ptr stream)
int fread(str buffer, int size, int count, ptr stream)
```

### 2. Archivo de Extension en el Proyecto
En `source/targets/c/extends/stdio.externs.egl`:
```easy-c
int puts(str s)
```

### 3. Consumo en `main.egl`
```easy-c
clause Target 'egl-c'
include "stdio" as IO

IO.puts("Mensaje emitido a traves de la funcion puts extendida")
```

El resultado de la fusion provee a `IO` el conjunto completo: `fopen`, `fclose`, `fseek`, `ftell`, `fread` y `puts`.
