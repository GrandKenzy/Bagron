# Arquitectura Del Compilador Bagron

Este documento detalla la arquitectura tecnica del compilador **Bagron**, sus principios de diseno, la integracion del frontend con **Gram** y **VNMA**, el procesador semantico y el backend LLVM.

---

## Principios De Diseño

Bagron fue concebido como un lenguaje de programacion de tipado estatico y sintaxis limpia basada en indentacion, con un objetivo estricto: **alto rendimiento sin intermediarios**.

**Anti sobrecarga de runtime (no runtime cost):**
Bagron no implementa recolector de basura (Garbage Collector), ni maquina virtual de bytecode, ni bucle de eventos oculto. Las estructuras definidas mapean directamente a nivel de memoria y los tipos escalares corresponden a anchos exactos de registros de la CPU.

**Separar fases:**
El pipeline de compilacion desacopla por completo el analisis sintactico del analisis semantico. El motor sintactico **Gram** no valida tipos ni resuelve simbolos; unicamente produce un arbol de sintaxis abstracta (AST). Es el procesador semantico quien aplica las reglas de inferencia, control de ambitos y compatibilidad binaria.

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

## Frontend Gramatical Y Gestion Con VNMA

### Integracion De Gram Mediante VNMA
Bagron aisla sus dependencias mediante el gestor de entornos **VNMA**, evitando la instalacion de paquetes globales en el sistema operativo:

- **Archivo `vnma.toml`:**
  Declara `gram` como dependencia local editable para desarrollo continuo:
  ```toml
  [project]
  name = "bagron"
  version = "0.3.0"

  [dependencies]

  gram = { path = "~/Desktop/Gram", editable = true }

  [dev-dependencies]

  [tool.vnma]
  vendor_dir = "vendor"
  ide_integration = ["vscode", "pycharm"]
  ```
- **Instalación (`vnma install`):**
  Para instalar solamente debes hacer vnma install dentro de tu proyecto.

- **Bloqueo reproducible (`vnma.lock`):**
  Congela la version exacta de Python y la fuente del framework sintactico para reproducibilidad binaria estricta.

- **Ejecucion (`vnma run`):**
  Las herramientas y pruebas se lanzan dentro del entorno gestionado (`vnma run`), resolviendo las importaciones de Gram sin inyectar rutas artificiales en `PYTHONPATH`.

- **Directorio `vendor/`:**
  Permite empaquetar o congelar las dependencias de Gram para compilacion local aislada sin requerir red.

### Configuracion Del Motor Lexico

- **importacion `import gram`:**
  Una vez instalado el Gram en el proyecto, se puede importar Gram sin problemas a nivel raiz o modulos profundos como si existiera en site-packages.

- **Uso de [Gram](https://github.com/GrandKenzy/Gram):**
  El uso de [Gram](https://github.com/GrandKenzy/Gram) corresponde a su documentacion. 

---

## Frontend Del Compilador

- **[Frontend Bagron (`core/frontend`)](./frontend_bagron.md):** Parser para sintaxis basada en indentacion (`.bg`). Consulta [Frontend Bagron](./frontend_bagron.md) para el detalle de reglas combinatorias, items y procesador.
- **[Backend LLVM (`core/backend/llvm`)](./backend_llvm.md):** Emision inicial de LLVM IR para simbolos globales validados.
