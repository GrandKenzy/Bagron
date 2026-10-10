# Deuda Técnica 01: Árbol de Expresiones Unificado en AST

## Estado
- **Prioridad:** Alta
- **Categoría:** Arquitectura / Frontend del Compilador
- **Impacto:** Expresiones complejas, anidamiento de operadores y robustez semántica

---

## 1. Contexto y Problema Actual

Actualmente, las expresiones en condiciones (`if`, `while`) y ciertas llamadas son procesadas mediante heurísticas locales (como `parse_condition_node` o inspección de secuencias planas de tokens).

Esto ocurrió porque en la gramática actual de `gram`, algunas expresiones relacionales y compuestas simplifican o aplanan la lista de tokens, perdiendo delimitadores como paréntesis de llamadas `(...)` o agrupaciones complejas cuando no están encapsuladas explícitamente en una regla especializada.

### Síntomas observados
- Se requiere inspeccionar manualmente llamadas internas (`cond_node.find('EGL_CALL') + cond_node.find('EGL_METHOD_CALL')`).
- Expresiones muy anidadas o combinadas (por ejemplo: `((x + y) * 2) > get_val(z)` o `a and not (b or c)`) requieren tratamientos particulares en cada visitante en vez de resolverse de forma uniforme.

---

## 2. Solución Requerida

Diseñar e implementar un generador y evaluador de expresiones unificado en el pipeline del compilador:

1. **Jerarquía Formal de Nodos de Expresión (AST):**
   - `BinaryExpr(left, op, right)`
   - `UnaryExpr(op, operand)`
   - `CallExpr(callee, args)`
   - `MemberAccessExpr(target, member)`
   - `LiteralExpr(value, type)`
   - `VariableExpr(name)`

2. **Visita Canónica Única:**
   - Un único visitante de expresiones (`visit_expression`) que tome cualquier nodo de expresión (sea en un `if`, `while`, asignación, retorno o argumento de función) y lo transforme a:
     - Un árbol semántico tipado en el procesador.
     - Su representación equivalente en C en el backend de forma recursiva.

---

## 3. Criterios de Aceptación

- [ ] Cualquier expresión matemática, lógica o relacional se evalúa recursivamente con precedencia estándar.
- [ ] No existen funciones auxiliares ad-hoc de "extracción de tokens" por sentencia (`_compile_condition` o similares que parseen cadenas planas).
- [ ] Las llamadas a funciones dentro de expresiones anidadas preservan sus tipos y argumentos sin requerir chequeos manuales.
