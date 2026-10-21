# Sistema De Modulos, Externs Y Extends

Este documento describe la arquitectura modular del compilador **Easy-C** (o **c-**), el mecanismo de resolucion topologica de dependencias, el algoritmo de mangling para aislamiento de simbolos y el subsistema de contratos externos (`.externs.egl`).

---

## Modulos Y Resolucion De Dependencias

Easy-C permite estructurar proyectos en multiples archivos `.egl` mediante las directivas `import` e `include`:

- **Directiva `import`:** Importa un modulo escrito en Easy-C. El analizador semantico procesa el archivo indicado, construye su tabla `Storage` y valida los tipos de sus simbolos publicos.
- **Directiva `include`:** Vincula una libreria o contrato C foraneo. Puede declararse de forma anonima o mediante alias cualificado (`include "sdl3" as C_SDL3`), exponiendo sus funciones bajo un prefijo ordenado.

### Prevencion De Recursion (`in_progress`)
Al procesar un modulo, el compilador registra su ruta canonica en el conjunto `storage.in_progress`. Si durante la construccion de dependencias un submodulo intenta importar un ancestro que aun no ha finalizado su analisis semantico, el compilador detecta el ciclo inmediatamente y evita bloqueos en memoria.

### Linearizacion Topologica (`ordered_modules`)
Cada vez que un modulo culmina exitosamente su procesamiento semantico, se incorpora a la lista `storage.ordered_modules`. Durante la emision final a C, los modulos se imprimen en este orden exacto:

```
       [ main.egl ]
        /        \
       v          v
   [ math.egl ]  [ vector.egl ]
        \        /
         v      v
      [ common.egl ]

   orden de emision en C:
   - common.egl
   - math.egl
   - vector.egl
   - main.egl
```

Este ordenamiento garantiza que cualquier typedef, struct o prototipo requerido por el modulo principal ya este declarado previamente en el archivo `program.c`.

---

## Protocolo De Name Mangling

Debido a que el lenguaje C carece de soporte nativo para espacios de nombres (namespaces), dos modulos de Easy-C podrian definir funciones con nombres identicos (por ejemplo, `init()`).

Para resolver esto en un unico archivo monolitico:
- **Modulo principal (`_main`):** Conserva los identificadores originales para respetar la compatibilidad con el punto de entrada estandar de la plataforma (`main`).
- **Submodulos (`_module`):** El compilador renombra las variables, funciones y estructuras internas anteponiendo un prefijo determinista derivado del nombre del modulo (`<modulo>_<simbolo>`):
  ```c
  // Definicion dentro de math.egl
  int math_calcular_distancia(int x, int y);
  ```

---

## Subsistema De Enlaces Foraneos (`.externs.egl`)

Para consumir bibliotecas de C sin incurrir en dependencias de runtime pesadas ni envoltorios manuales, c- utiliza contratos foraneos ubicados en archivos `.externs.egl`:

- **Metadatos y directivas del enlazador:**
  - `@header <ruta.h>`: Inserta la cabecera del sistema en el archivo `program.c`.
  - `@link <biblioteca>`: Agrega la bandera de enlazado al compilador nativo (ej. `-lSDL3`).
  - `@bin <archivo>`: Declara el binario dinamico en tiempo de ejecucion (`.dll`, `.so`).
  - `@lib_dir <ruta>`: Agrega rutas de busqueda de librerias (`-L`).
  - `@include_dir <ruta>`: Agrega rutas de cabeceras C (`-I`).

- **Gramatica de firmas C:**
  Gram parsea directamente declaraciones de funciones ANSI C o firmas idiomaticas de Easy-C, registrandolas en `storage.externs` para permitir llamadas con chequeo estricto de tipos.

---

## Guias Adicionales

Para un ejemplo completo de integracion practica con librerias dinamicas de alto rendimiento, consulta:
- **[Integracion De Librerias Compiladas](./librerias_compiladas.md):** Procedimiento para enlazar bibliotecas nativas C/C++ tomando como caso de estudio real la integracion con SDL3.
