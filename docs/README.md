# Documentacion Tecnica De Easy-C y compilador (ECC)

Especificacion de arquitectura y manual tecnico del compilador **ECC** y el lenguaje **EasyC (EC)**

---

## Modulos De Documentacion

* NOTA: Por definir.

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

## Mapa Del Repositorio

* NOTA: Por definir.