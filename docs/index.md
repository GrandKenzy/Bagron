# Documentacion Tecnica de Easy-C (EGL)

Easy-C (EGL) es un lenguaje de programacion de tipado estatico y sintaxis limpia diseñado para compilar de forma agnostica y generar codigo C monolítico de alto rendimiento (C99/C11). Su arquitectura desacopla el analisis sintactico, el procesamiento semantico intermedio y la emision de codigo destino, permitiendo interoperabilidad nativa con librerias en C mediante un subsistema de definiciones externas (`externs`) y extensiones del usuario (`extends`).

El compilador incluye un resolvedor de dependencias modulares con soporte de name mangling, un sistema de deteccion automatica de cabeceras C estandar (`stdint.h`, `stdbool.h`, `stdio.h`, `stdlib.h`), verificacion estricta de clausulas de entorno y un punto de entrada CLI multiplataforma (`egl.py` / `egl.bat`).

---

## Arquitectura del Sistema

El flujo de transformacion de Easy-C opera en cinco etapas secuenciales:

1. **Frontend Gramatical (Lexing y Parsing):** El motor `gram` procesa el codigo fuente aplicando reglas sintacticas combinatorias para generar un arbol de sintaxis abstracta (`ASTProgram`).
2. **Analisis Modular y Mangling:** El compilador rastrea dependencias importadas (`import`), valida la coherencia de la clausula `Target` y renombra los simbolos de modulo bajo el patron `inmodule_<modulo>_<simbolo>`, reescribiendo los nodos de llamada correspondientes.
3. **Procesamiento Semantico:** El subsistema `core.processor` recorre el AST jerarquico y genera instancias de objetos semanticos (`Variable`, `Function`, `Call`, `MethodCall`, etc.), validando contratos de tipos y resolviendo namespaces.
4. **Emision de Backend C:** El modulo `core.backend.c` transforma los objetos semanticos en instrucciones C, resolviendo tipos equivalentes, deduciendo llamadas del sistema (`deffunc`), gestionando llamadas inline y detectando directivas `#include`.
5. **Ensamblado Monolitico y Ejecucion:** Se consolidan prototipos adelantados (*forward declarations*), estructuras, funciones de modulo y sentencias raiz dentro de una funcion `main` sintetica en un unico archivo monolítico (`program.c`), opcionalmente compilado y ejecutado via GCC.

---

## Mapa de Documentacion

### 1. Arquitectura del Compilador
* **[Vision General de Arquitectura](01-Arquitectura/index.md):** Ciclo de vida de compilacion, capas del sistema y flujo de datos.
* **[Frontend y Gramatica](01-Arquitectura/frontend_gramatica.md):** Tokenizador, reglas BNF de `core/initiator/rules` y estructura de nodos AST.
* **[Procesador Semantico y Tipos](01-Arquitectura/procesador_semantico.md):** Modelo de objetos semanticos, catalogo de tipos y resolucion de ambitos.
* **[Backend C y Ensamblador Monolitico](01-Arquitectura/backend_c.md):** Generacion de codigo C, emision de funciones y deduplicacion de cabeceras.

### 2. Modulos, Externs y Extends
* **[Vision General de Modulos y Externs](02-Modulos-y-Externs/index.md):** Ecosistema de integracion, archivos de definicion y aislamiento.
* **[Sistema de Modulos y Mangling](02-Modulos-y-Externs/modulos_y_mangling.md):** Resolucion de `import`, verificacion de Target y reescritura de simbolos.
* **[Includes y Externs](02-Modulos-y-Externs/externs_e_includes.md):** Semantica de `include` con y sin alias, parser de `.externs.egl` y cache binario.
* **[Sistema Extends](02-Modulos-y-Externs/sistema_extends.md):** Fusión transparente de librerias del usuario en `source/targets/<backend>/extends/`.
* **[Librerias Compiladas Nativas (SDL3)](02-Modulos-y-Externs/librerias_compiladas.md):** Guia paso a paso para anadir e integrar bibliotecas compiladas C/C++ (`.dll`, `.a`, `.so`) con directivas `@header`, `@link` y `@bin`.

### 3. Guia del Colaborador
* **[Vision General del Colaborador](03-Guia-del-Colaborador/index.md):** Requisitos de desarrollo, organizacion de carpetas y flujo de trabajo.
* **[Convenciones de Codigo](03-Guia-del-Colaborador/convenciones_codigo.md):** Invariantes de ingeniería (cero comentarios Python, tipado, mutabilidad).
* **[Creacion de Nuevas Reglas](03-Guia-del-Colaborador/creacion_de_reglas.md):** Guia paso a paso para extender la gramatica y los visitantes de emision.
* **[CLI y Herramientas](03-Guia-del-Colaborador/cli_y_herramientas.md):** Uso, mantenimiento y ampliacion de comandos de consola.

### 4. Referencia del Lenguaje y Diagnosticos
* **[Vision General de Referencia](04-Referencia/index.md):** Indice de especificaciones normativas y tablas tecnicas.
* **[Tipos, Palabras Clave y Clausulas](04-Referencia/tipos_y_palabras_clave.md):** Matriz de tipos nativos, propiedades magicas y clausulas de entorno.
* **[Catalogo de Diagnosticos y Errores](04-Referencia/errores_y_diagnostico.md):** Matriz de excepciones, causas raices y procedimientos de resolucion.

---

## Inicio Rapido

### Requisitos del Sistema
* Python 3.10 o superior instalado en el entorno.
* Compilador de C (GCC o Clang) accesible en el PATH del sistema para ejecucion directa.

### Estructura Minima de Proyecto EGL

```
mi_proyecto/
├── main.egl
└── modules/
    └── matematicas.egl
```

Contenido de `modules/matematicas.egl`:
```easy-c
clause Target 'egl-c'

int duplicar(int n):
    return n * 2
```

Contenido de `main.egl`:
```easy-c
clause Target 'egl-c'

include "stdio"
import matematicas

int valor = 21
int resultado = matematicas.duplicar(valor)
print("Resultado:", resultado)
```

### Comandos de Compilacion y Ejecucion

Compilacion generando archivo C monolitico:
```bash
python egl.py compile mi_proyecto -o program.c
```

Compilacion y ejecucion directa con GCC:
```bash
python egl.py compile mi_proyecto -o program.c --run
```

En entornos Windows mediante el lanzador batch:
```cmd
egl.bat compile mi_proyecto --run
```
