# Documentacion Tecnica De Bagron

Especificacion de arquitectura y manual tecnico del compilador y el lenguaje **Bagron**

---

## Modulos De Documentacion

- **01. Arquitectura:**
  - [Arquitectura Del Compilador Bagron](01-Arquitectura/index.md): Diseno general, pipeline, integracion con Gram y VNMA.
  - [Frontend Bagron](01-Arquitectura/frontend_bagron.md): Reglas combinatorias por indentacion, clausulas y procesador semantico de Bagron.

- **02. Modulos Y Externs:**
  - [Sistema De Modulos, Externs Y Extends](02-Modulos-y-Externs/index.md): Resolucion de dependencias, name mangling y contratos foraneos.
  - [Integracion De Librerias Compiladas](02-Modulos-y-Externs/librerias_compiladas.md): Enlace de bibliotecas nativas de alto rendimiento.

- **03. Guia Del Colaborador:**
  - [CLI Y Herramientas](03-Guia-del-Colaborador/cli_y_herramientas.md): Interfaz de comandos, lanzador nativo Win32, extension VS Code y telemetria.

- **04. Referencia:**
  - [Tipos, Palabras Clave Y Metapropiedades](04-Referencia/tipos_y_palabras_clave.md): Matriz de tipos nativos, precedencia y catalogo reservado.

---

## Pipeline Global De Compilacion

```
+-----------------------------------------------------------------------------+
|                         Pipeline global Bagron                              |
+-----------------------------------------------------------------------------+
   [ Codigo Fuente (.bg) ]
              |
   Tokens     v      Gram
   +----------------------+   Configuracion de Frontend (Bagron)
   |  Gram Lexer Engine   |   y registro de palabras claves y reglas sintácticas.
   +----------------------+
              |
   AST        v      Gram
   +----------------------+   Evaluacion y parseo usando las reglas sintácticas.
   | Gram Parser Engine   |   Generación de un AST Nodeizado.
   +----------------------+
              | 
   Semantic   v       Bagron
   +----------------------+   Resolucion de ambitos, tabla de simbolos
   | Semantic Processor   |   proyectos modularizados y otras dependencias.
   +----------------------+   Generación de objetos.
              | 
   Opt. F1    v       Bagron
   +----------------------+   Eliminación de código muerto, alineamiento y reorder.
   |  Optimizations P1    |   Constant Folding y Type Checker.
   +----------------------+   Protección ligera de memoria y diagnosticos legibles.
              |
   IR Común   v       Bagron
   +----------------------+   
   |     IR Generation    |   Generación de IR para LLVM.
   +----------------------+
              |
   Opt. F2    v       LLVM
   +----------------------+   
   |  Optimizations P2    |   Optimizaciones que aplique LLVM.
   +----------------------+
              |
              v       
   [ LLVM Backend ] ----> Binario Nativo
```

---

## Mapa Del Repositorio

* NOTA: Por definir.
