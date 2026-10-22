# Arquitectura Del Compilador Easy-C (EC)

Este documento detalla la arquitectura tecnica del compilador **Easy-C** (nombrado tambien como **EC**), sus principios de diseno, la integracion del frontend con **Gram** y **VNMA**, el procesador semantico y el backend LLVM.

---

## Principios De Diseño

Easy-C fue concebido como un lenguaje de programacion de tipado estatico y sintaxis limpia basada en indentacion, con un objetivo estricto: **Interoperar con C mientras EC también sea un lenguaje de alto rendimiento sin intermediarios**.

**anti sobre carga de runtime (no runtime cost):**
c- no implementa recolector de basura (Garbage Collector), ni maquina virtual de bytecode, ni bucle de eventos oculto. Las estructuras definidas en Easy-C mapean directamente como structs estandar de C, y los tipos escalares corresponden a anchos exactos de registros de la CPU.

**separar fases:**
El pipeline de compilacion desacopla por completo el analisis sintactico del analisis semantico. El motor sintactico **Gram** no valida tipos ni resuelve simbolos; unicamente produce un arbol de sintaxis abstracta (AST). Es el procesador semantico (`core/processor`) quien aplica las reglas de inferencia, control de ambitos y compatibilidad binaria.

---

## Pipeline Global De Compilacion

```
+-----------------------------------------------------------------------------+
|                      Pipeline global Easy-C (C-)                            |
+-----------------------------------------------------------------------------+
   [ Codigo Fuente (.egl) ]
              |
   Tokens     v      Gram
   +----------------------+   Configuracion global de Frontend (C/EC)
   |  Gram Lexer Engine   |   y registro de palabras claves y reglas sintácticas.
   +----------------------+
              |
   AST        v      Gram
   +----------------------+   Evaluacion y parseo usando las reglas sintácticas.
   | Gram Parser Engine   |   Generación de un AST Nodeizado.
   +----------------------+
              | 
   Semantic   v       ECC
   +----------------------+   Resolucion de ambitos, tabla de simbolos
   | Semantic Processor   |   proyectos modularizados y otras dependencias.
   +----------------------+   Generación de objetos.
              | 
   Opt. F1    v       ECC
   +----------------------+   Eliminación de código muerto, alineamiento y reorder.
   |  Optimizations P1    |   Constant Folding y Type Checker.
   +----------------------+   Protección ligera de memoria y diagnosticos legibles.
              |
   IR Común   v       ECC
   +----------------------+   
   |     IR Generation    |   Generación de IR (C/EC) para LLVM.
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
Easy-C aisla sus dependencias mediante el gestor de entornos **VNMA**, evitando la instalacion de paquetes globales en el sistema operativo:

- **Archivo `vnma.toml`:**
  Declara `gram-framework` como dependencia local editable para desarrollo continuo:
  ```toml
  [project]
  name = "easyc"
  version = "0.3.0"

  [dependencies]

  gram-framework = { git = "https://github.com/GrandKenzy/Gram.git", branch="main" }

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

- **importación `import gram`:**
  Una vez instalado el Gram en el proyecto, se puede importar Gram sin problemas a nivel raíz o módulos profundos como si existiera en site-packages.

- **Uso de [Gram](https://github.com/GrandKenzy/Gram):**
  El uso de [Gram](https://github.com/GrandKenzy/Gram) corresponde a su documentación. 
