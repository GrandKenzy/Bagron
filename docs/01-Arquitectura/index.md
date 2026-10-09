# Arquitectura del Compilador

Esta seccion detalla el diseño interno y el ciclo de vida del compilador de Easy-C (EGL). La arquitectura esta diseñada bajo el principio de separacion estricta de responsabilidades, dividiendo el pipeline en analisis lexico y sintactico, reescritura de dependencias modulares, transformacion semantica intermedia y generacion de codigo C optimizado.

---

## Modulos y Especificaciones

* **[Frontend y Gramatica](frontend_gramatica.md):** Analisis del motor `gram`, definicion combinatoria de reglas sintacticas en `core/initiator/rules` y estructura jerarquica del arbol sintactico (`ASTProgram`).
* **[Procesador Semantico y Tipos](procesador_semantico.md):** Transformacion de nodos AST en objetos semanticos de `core/processor/objects`, resolucion del sistema de tipos estatico y gestion de ambitos.
* **[Backend C y Ensamblador Monolitico](backend_c.md):** Emision de codigo C99/C11, inferencia estatica de dependencias `#include`, expansion de llamadas del sistema e integracion monolitica en `program.c`.

---

## Flujo de Trabajo del Compilador

El ciclo de transformacion desde el codigo fuente hasta el binario ejecutable se describe en el siguiente flujo secuencial:

```
[Codigo EGL: main.egl y modules/*.egl]
                 │
                 ▼
     [Frontend: gram.process]
       - Tokenizacion con Token y CustomToken
       - Aplicacion de reglas combinatorias (core.grammar)
       - Construccion de ASTProgram
                 │
                 ▼
 [Resolucion Modular y Mangling: core.compiler]
       - Validacion estricta de clause Target
       - Asignacion de valores por defecto de la plataforma
       - Mangling de identificadores (inmodule_<mod>_<sym>)
       - Reescritura de nodos de llamada (EGL_CALL / EGL_METHOD_CALL)
                 │
                 ▼
   [Pase Semantico: core.processor.process]
       - Creacion de objetos: Variable, Function, Call, etc.
       - Carga de externs y validacion de firmas
       - Registro en el diccionario global base.ITEMS
                 │
                 ▼
       [Backend C: core.backend.c.process]
       - Deteccion automatica de cabeceras (detectors.py)
       - Conversion de tipos (resolve_c_type)
       - Compilacion de funciones y sentencias (deffunc, visitors)
                 │
                 ▼
[Ensamblador Monolitico: compile_project]
       - Deduplicacion de #include y typedefs
       - Emision de prototipos adelantados (forward declarations)
       - Emision de funciones de modulos
       - Envoltura de sentencias raiz en int main(int argc, char** argv)
                 │
                 ▼
      [Salida: program.c / program.exe]
```
