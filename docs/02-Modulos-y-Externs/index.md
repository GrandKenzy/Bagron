# Sistema de Modulos, Externs y Extends

Esta seccion documenta el subsistema de modularizacion e integracion con codigo foraneo de Easy-C (EGL). Se analizan los mecanismos que permiten estructurar proyectos grandes en multiples archivos fuente, el protocolo de colision mediante *name mangling*, la especificacion de cabeceras de librerias nativas (`externs`) y la capacidad de los proyectos de extender o sobreescribir definiciones del backend mediante `extends`.

---

## Modulos y Especificaciones

* **[Sistema de Modulos y Mangling](modulos_y_mangling.md):** Convenciones de ubicacion de modulos, resolucion jerarquica de dependencias, verificacion de la clausula `Target` y renombrado de simbolos (`inmodule_`).
* **[Includes y Externs](externs_e_includes.md):** Sintaxis de `include` con y sin alias (`as`), especificacion de archivos `.externs.egl`, serializacion en cache binario y resolucion de tipos C foraneos.
* **[Sistema Extends](sistema_extends.md):** Mecanismo de extension modular local en `source/targets/<backend>/extends/` y estrategia de fusion no destructiva con librerias del sistema.
* **[Librerias Compiladas Nativas (SDL3)](librerias_compiladas.md):** Guia paso a paso para anadir e integrar bibliotecas compiladas C/C++ (`.dll`, `.a`, `.so`) con directivas `@header`, `@link` y `@bin`.

---

## Resumen del Ecosistema de Integracion

El compilador distingue claramente entre dos fuentes de codigo externo:

1. **Modulos EGL y Librerias de Target (`import`):**
   * Codigo fuente nativo escrito en Easy-C ubicado en `source/modules/<nombre>.egl`, en librerias de proyecto `source/targets/<backend>/libraries/<nombre>.egl` o en librerias base del compilador (`core/backend/<backend>/libraries/<nombre>.egl`).
   * Se compila junto con el proyecto y sus funciones son renombradas con prefijo de modulo para evitar colisiones en C.
2. **Librerias Nativas del Backend (`include`):**
   * Cabeceras de C (ej. `stdio`, `stdlib`, `string`) cuyas firmas estan documentadas en archivos `.externs.egl`.
   * Pueden incluirse de forma anonima (solo directiva C `#include <lib.h>`) o con espacio de nombres (`include "lib" as ALIAS`) para invocar sus funciones mediante prefijo cualificado.
   * El desarrollador puede enriquecer las firmas existentes mediante la carpeta `source/targets/<backend>/extends/`.
