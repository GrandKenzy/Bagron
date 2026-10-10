# Registro de Deudas Técnicas y Refactorizaciones Pendientes

Este directorio registra los puntos de deuda técnica identificados en el desarrollo de **Easy-C (EGL)** para mantener la arquitectura limpia, escalable y sin soluciones ad-hoc repetitivas.

---

## Índice de Deudas

| ID | Título | Prioridad | Estado | Archivo |
| :--- | :--- | :--- | :--- | :--- |
| **01** | Árbol de Expresiones Unificado en AST | Alta | Pendiente | [01_arbol_expresiones_ast.md](./01_arbol_expresiones_ast.md) |
| **02** | Migración de Tipos Simples a `Type` | Media | Completado | [02_migracion_tipos_simples_a_struct_type.md](./02_migracion_tipos_simples_a_struct_type.md) |

---

## Principio de Diseño
> *"Lo ideal es no hacer magia y hacer una salida para cada caso, sino delegar a una sola salida; de lo contrario, después tendremos varias formas y todo será inmantenible."*
