# Deuda Técnica 01: Árbol de Expresiones Unificado en AST

## Estado
- **Prioridad:** Alta
- **Categoría:** Arquitectura / Frontend del Compilador
- **Impacto:** Expresiones complejas, anidamiento de operadores y robustez semántica
- **Estado Actual:** Resuelta (Completada)

---

## 1. Contexto y Problema Original

Anteriormente, las expresiones en condiciones (`if`, `while`), asignaciones y llamadas eran procesadas mediante heurísticas locales (inspección de secuencias planas de tokens, concatenación de cadenas y expresiones regulares ad-hoc).

Esto causaba inconsistencias en expresiones anidadas, pérdida de tipos en llamadas compuestas y falta de recursividad formal.

---

## 2. Solución Implementada

Se implementó el pipeline canónico y unificado de expresiones:

1. **Jerarquía Formal de Nodos de Expresión (AST) en `core/processor/objects/expression.py`:**
   - `BinaryExpr(left, op, right)`: Operaciones binarias con asociatividad formal.
   - `UnaryExpr(op, operand)`: Operadores unarios (`-`, `+`, `!`, `not`, `&`, `*`, `~`).
   - `LiteralExpr(value, type)`: Literales numéricos, booleanos, cadenas, caracteres y null.
   - `VariableExpr(name)`: Identificadores y referencias a variables o símbolos.
   - `IndexAccess(target, index)`: Indexación recursiva de arreglos y punteros.
   - Integración nativa con `Call`, `MethodCall` y `MemberAccess`.

2. **Visitante Canónico en `core/processor/visitors/expression.py`:**
   - Transforma nodos de gramática de expresiones (`EGL_EXPRESSION`, `EGL_LOGICAL_AND`, `EGL_ADDITIVE`, etc.) preservando la precedencia de operadores.
   - Aplica plegado asociativo a la izquierda para operadores estándar y asociativo a la derecha para potencias (`**`).

3. **Generación Recursiva en Backend C (`core/backend/c/visitors/expression.py`):**
   - Función única `format_expression(raw, block)` que evalúa recursivamente cualquier nodo del árbol de expresiones AST y produce código C canónico.
   - Todas las sentencias (`if`, `while`, `var_decl`, `assign`, `return`, `call`, `method_call`) delegan a este pipeline único.

---

## 3. Criterios de Aceptación

- [x] Cualquier expresión matemática, lógica o relacional se evalúa recursivamente con precedencia estándar.
- [x] No existen funciones auxiliares ad-hoc de extracción plana de tokens por sentencia.
- [x] Las llamadas a funciones dentro de expresiones anidadas preservan sus tipos y argumentos sin requerir chequeos manuales.
