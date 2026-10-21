# Documentacion Tecnica De Easy-C (c-)

Especificacion de arquitectura y manual tecnico del compilador **Easy-C** (o **c-**), transpilador estatico de alto rendimiento enfocado en la emision de codigo C monolitico (C99/C11) sin sobrecarga de runtime ni recoleccion de basura.

---

## Modulos De Documentacion

El repositorio organiza su suite tecnica en las siguientes secciones:

- **[Arquitectura del Compilador](./01-Arquitectura/index.md):** Frontend gramatical con Gram y VNMA, procesador semantico y emision de backend C.
- **[Modulos, Externs y Extends](./02-Modulos-y-Externs/index.md):** Sistema de modulos, resolucion topologica de dependencias y aislamiento de espacios de nombres.
- **[Integracion de Librerias Compiladas](./02-Modulos-y-Externs/librerias_compiladas.md):** Guia para enlazar bibliotecas nativas C/C++ usando SDL3 como ejemplo guiado.
- **[CLI y Herramientas](./03-Guia-del-Colaborador/cli_y_herramientas.md):** Guia detallada de comandos de consola, flags del compilador, entorno VNMA y empaquetado VSIX.
- **[Referencia de Tipos y Palabras Clave](./04-Referencia/tipos_y_palabras_clave.md):** Matriz de tipos nativos, propiedades magicas y catalogo de operadores del lenguaje.

---

## Pipeline Global De Compilacion

```
+-----------------------------------------------------------------------------+
|                      Pipeline global Easy-C (C-)                            |
+-----------------------------------------------------------------------------+
   [ Codigo Fuente (.egl) ]
              |
              v
   +----------------------+   Configuracion global de comentarios (;)
   |  Gram Lexer Engine   |   y registro de palabras clave y tipos.
   +----------------------+
              | Tokens
              v
   +----------------------+   Evaluacion determinista y backtracking
   | Gram Parser Engine   |   mediante Combinadores (Seq, Alt, DualExpr).
   +----------------------+
              | AST (ast.ASTRef)
              v
   +----------------------+   Resolucion de ambitos, tabla de simbolos
   | Semantic Processor   |   (Storage), inferencia de tipos (typesys.py)
   +----------------------+   y creacion de Objetos Semanticos.
              | Objetos Semanticos tipados
              v
   +----------------------+   Mangling reproducible, ordenamiento topologico
   |  Backend Monolitico  |   de modulos y emision directa a C99/C11.
   +----------------------+
              |
              v
   [ build/program.c ] ----> [ Compilador C (GCC / Clang / MSVC) ] ----> Binario Nativo
```

---

## Mapa Del Repositorio

| Directorio / Archivo | Responsabilidad Tecnica | Seccion Documentada |
| :--- | :--- | :--- |
| `vnma.toml` / `vnma.lock` | Gestion de dependencias de Gram y aislamiento de entorno virtual. | [01-Arquitectura](./01-Arquitectura/index.md), [03-Guia-del-Colaborador](./03-Guia-del-Colaborador/cli_y_herramientas.md) |
| [`core/compiler.py`](../core/compiler.py) | Punto de entrada del pipeline de compilacion. | [01-Arquitectura](./01-Arquitectura/index.md) |
| [`core/grammar.py`](../core/grammar.py) | Reglas sintacticas raiz y punto de entrada `ENTRYPOINT`. | [01-Arquitectura](./01-Arquitectura/index.md) |
| [`core/initiator/`](../core/initiator) | Declaracion lexica y reglas sintacticas con combinadores de Gram. | [01-Arquitectura](./01-Arquitectura/index.md) |
| [`core/processor/`](../core/processor) | Tabla de simbolos (`Storage`), sistema de tipos y visitantes semanticos. | [01-Arquitectura](./01-Arquitectura/index.md) |
| [`core/backend/ec/`](../core/backend/ec) | Generador de codigo C monolitico (`program.c`). | [01-Arquitectura](./01-Arquitectura/index.md) |
| [`core/externs/`](../core/externs) | Enlace y analisis de cabeceras externas C (`.externs.egl`). | [02-Modulos-y-Externs](./02-Modulos-y-Externs/index.md) |
| [`core/packages/`](../core/packages) | Gestor de paquetes y librerias (`.lib.egl`). | [02-Modulos-y-Externs](./02-Modulos-y-Externs/index.md) |
| [`tools/`](../tools) | Lanzador nativo Win32 en C (`egl.exe`), instalador y diagnosticos. | [03-Guia-del-Colaborador](./03-Guia-del-Colaborador/cli_y_herramientas.md) |
