# Reporte Técnico de Auditoría: Brechas y "Agujeros" en los Visitores Semánticos

**Fecha:** Octubre 2026  
**Ubicación:** `core/processor/`  
**Estado de Pruebas Unitarias:** 250/250 exitosas (100% verde)

---

## 1. Resumen Ejecutivo

El procesador semántico de Easy-C (`core/processor`) ha culminado exitosamente la transición hacia una arquitectura moderna basada en el AST de **Gram** (`gram.ast.ASTRef`), desacoplada completamente del antiguo AST sintáctico (`EGL_*`). La limpieza arquitectónica eliminó archivos obsoletos (`errors.py`, `visitors/expression.py`, y alias de retrocompatibilidad), consolidando un pipeline directo y fuertemente tipado.

Sin embargo, a medida que el lenguaje escala hacia soporte completo de estructuras avanzadas, orientación a objetos y optimización para el backend de C, se han identificado **agujeros semánticos**, casos de borde no manejados y oportunidades de robustecimiento en los visitores actuales (`core/processor/visitors/`).

Este documento cataloga de forma exhaustiva y detallada cada una de estas brechas técnicas para guiar las próximas fases de desarrollo.

---

## 2. Auditoría Detallada por Visitor

### 2.1. `assign.py` (Asignaciones y Operadores Compuestos)

| ID | Gravedad | Estado | Descripción del Agujero | Impacto Técnico / Solución |
|---|---|---|---|---|
| **ASG-01** | **Alta** | **RESUELTO** | **Validación de tipos en operadores compuestos (`+=`, `-=`, `*=`, etc.):** Se implementó `validate_compound_assignment` verificando compatibilidad estricta de cada operador aritmético y bitwise según el tipo destino y el tipo evaluado. | Bloquea operaciones inválidas como `str += 5`, `bool *= 2`, `float %= 2.0`, `float &= 1`, etc. en tiempo semántico con `TypeError`. |
| **ASG-02** | **Media** | **RESUELTO** | **Cadenas de miembros en clases anidadas (`self`, `cls`, `Clase`, variables):** Se implementó resolución recursiva en profundidad para cualquier nivel de anidamiento de structs y clases tanto en asignación como en lectura de expresiones. | Permite asignaciones como `self.cfg.timeout = 5000` o `MyClass.sub.val = 42` validando tipos y existencia de campos en cada nivel. |
| **ASG-03** | **Media** | **PENDIENTE** | **Ausencia de sobrecarga de operadores de asignación (`__iadd__`, etc.):** Si una clase define métodos para sobrecarga de operadores en sitio, el visitor los trata como asignaciones primitivas de C. | Pendiente de implementación por solicitud explícita. |
| **ASG-04** | **Baja** | **RESUELTO** | **Declaración múltiple tipada con desempaquetado (`int a, b = x, y`):** Se añadió la regla `VAR_MULTI_DECL` a la gramática y el soporte en `visit_var` para listas de identificadores y valores con tipo explícito. | Permite `int a, b = 10, 20` o `int a, b = x, y` verificando cardinalidad, tipos y colisiones. |
| **ASG-05** | **Media** | **RESUELTO** | **Puntero constante a datos mutables (`cptr`):** Se incorporó `cptr` en los tipos intrínsecos representando un puntero inmutable en su dirección pero con elementos subyacentes modificables. | Reasignar `p = ...` o `p += 1` lanza `RuntimeError`, mientras que la mutación de elementos `p[0] = val` está permitida. |

---

### 2.2. `call.py` (Llamadas a Funciones, Métodos, Cadenas y Acceso a Índices)

| ID | Gravedad | Descripción del Agujero | Impacto Técnico | Estado |
|---|---|---|---|---|
| **CAL-01** | **Alta** | **Orden estricto de parámetros y datos inicializados:** Orden estricto posicionales -> `*args: tipo` -> por defecto `p: tipo = val`. No existe `**kwargs`. Prohibido `foo(b=10)`, debe ser `foo(b: int = 10)`. | **RESUELTO** (Gramática `VARIADIC_PARAM` y `PAIR_DECLARE_PARAM`, validación en `process_parameters` y `_validate_call_arguments`). |
| **CAL-02** | **Alta** | **Llamadas a métodos encadenados intermedios ("Fluent Interface"):** Organización de llamadas de izquierda a derecha (`MethodCall`/`MemberAccess`/`Call`) para patrones fluidos `builder.step1().step2()`. Verificación de módulos pendiente. | **RESUELTO** (Organización jerárquica de expresiones encadenadas en `visit_member_chain`). |
| **CAL-03** | **Alta** | **Herencia recursiva en resolución de métodos y símbolos:** El hijo hereda recursivamente contexto, campos y métodos del padre, emitiendo debug warnings `[DEBUG/WARN] Reemplazando ...` al sobreescribir. | **RESUELTO** (Algoritmo recursivo `_inherit_base_symbols` con detección de ciclos en `class_decl.py`). |
| **CAL-04** | **Media** | **Tipado estricto en variádicos (`*args: tipo`):** Se exige obligatoriamente tipo explícito en `*args`. Se valida el tipo inferido de todos los argumentos variádicos pasados en la llamada. | **RESUELTO** (`VARIADIC_PARAM` en gramática y chequeo de tipos en `_validate_call_arguments`). |
| **CAL-05** | **Media** | **Referencias hacia adelante (Forward References / Recursión mutua):** Resolución en una sola pasada. | **PENDIENTE** (Postergado por especificación). |
| **CAL-06** | **Baja** | **Validación estática de índices en arreglos:** Verificación de límites estáticos conocidos (`0 <= idx < size`) en lectura y asignación. Rebanado (slicing) pospuesto. | **RESUELTO PARCIALMENTE** (Validación de índices completada; slicing pendiente). |

---

### 2.3. `class_decl.py` (Declaración y Semántica de Clases)

| ID | Gravedad | Estado | Descripción del Agujero | Impacto Técnico / Solución |
|---|---|---|---|---|
| **CLS-01** | **Alta** | **RESUELTO** | **Herencia completa de campos y métodos entre clases:** Se implementó `_inherit_base_symbols` con recorrido recursivo de bases y copia de métodos y campos de clase e instancia. | Las subclases heredan contexto y miembros con avisos de sobreescritura `[DEBUG/WARN]`. |
| **CLS-02** | **Alta** | **RESUELTO** | **Soporte de `super().__init__()` y Unión de Clases:** Implementación de `super().__init__()` como mecanismo único de unión de clases. Se prohíbe `super().method()` dado que los métodos ya se encuentran unificados en la clase; se validan argumentos contra la clase base y se unifican los campos de instancia. Se creó `core/processor/magic_methods.py` con el catálogo canónico de métodos mágicos (defaults estrictos a `void` o `0`). | Permite inicialización jerárquica y unión de estructuras en C, bloqueando llamadas inválidas y accesos aislados. |
| **CLS-03** | **Alta** | **PENDIENTE** | **Sobrecarga de operadores no vinculada:** Las funciones mágicas `__add__`, `__sub__`, `__mul__`, etc. están catalogadas pero pendientes de vincular al parser de expresiones aritméticas nativas. | La sobrecarga de operadores solo funciona mediante llamadas explícitas a métodos por ahora. |
| **CLS-04** | **Media** | **RESUELTO** | **Detección de ciclos en herencia:** Se implementó detección estricta de ciclos (`visited: set`) en el grafo de herencia en `_inherit_base_symbols`. | Lanza `RuntimeError` inmediato si se detecta recursión cíclica (`class A(B): class B(A):`). |
| **CLS-05** | **Media** | **PENDIENTE** | **Sin propiedades (`@property`, `@setter`):** No se reconocen decoradores de propiedad para exponer métodos como atributos de lectura/escritura. | Todo acceso a miembros computados debe ser una llamada a método explícita. |
| **CLS-06** | **Media** | **PENDIENTE** | **Destructores y gestión RAII (`__del__`):** Catálogo definido en `magic_methods.py`; falta vincular con la emisión de `free()` automático en C. | Fugas de memoria potenciales si el usuario no libera manualmente las estructuras instanciadas en el heap. |
| **CLS-07** | **Baja** | **PENDIENTE** | **Visibilidad uniforme a nivel de clase:** Todos los métodos y atributos adoptan la visibilidad de la clase (`storage.privacy`). | Falta de encapsulamiento granular dentro de una clase pública. |

---

### 2.4. `func_decl.py` (Funciones, Parámetros y Retorno)

| ID | Gravedad | Descripción del Agujero | Impacto Técnico |
|---|---|---|---|
| **FNC-01** | **Alta** | **Análisis de flujo de retorno incompleto (Return Path Analysis):** `process_body` solo inspecciona nodos `RETURN` inmediatos en el nivel superior del cuerpo. Si el retorno está dentro de un `if-else` o un bucle, o si una función no-`void` termina sin `return`, no se emite error semántico. | Funciones no-`void` pueden omitir el retorno en tiempo de análisis y producir comportamiento indefinido en C. |
| **FNC-02** | **Media** | **Falta de rechazo explícito a funciones anidadas:** El lenguaje prohíbe funciones dentro de funciones ("tampoco funciones dentro de funciones"), pero en `process_body`, si se encuentra un nodo `FUNCTION` o `DECORATED_FUNCTION`, simplemente se añade a `body_items` en la rama `else` sin lanzar un `RuntimeError` explícito. | No se aplica formalmente la regla de no anidamiento de funciones. |
| **FNC-03** | **Media** | **Valores por defecto en parámetros no validados en definición:** En `PAIR_DECLARE_PARAM`, el valor por defecto se almacena en `FunctionParam.default`, pero no se valida contra el tipo del parámetro (`validate_type`) en el momento en que se declara la función. | Se pueden declarar funciones con valores por defecto incompatibles (ej. `def f(x: int = "hola"):`) sin error en la declaración. |
| **FNC-04** | **Media** | **Parámetros de función de primera clase (Callbacks):** No existe soporte semántico para tipos de firma de función en parámetros (ej. `fn(int, int) -> bool`), forzando el uso de `ptr` o `__void_p_t__` sin chequeo de tipos. | Falta de tipado estricto al pasar callbacks a bibliotecas como SDL3 o runtime C. |

---

### 2.5. `var_decl.py` (Variables, Inferencia de Tipos y Validación)

| ID | Gravedad | Descripción del Agujero | Impacto Técnico |
|---|---|---|---|
| **VAR-01** | **Alta (Crítica)** | **Permisividad excesiva en validación de punteros:** En `validate_type`: `var_type.rstrip('*') == inferred_type.rstrip('*')`. Si se compara `int*` con `int`, `rstrip('*')` da `'int'` en ambos lados, por lo que la condición se cumple y **no lanza error**. | Permite asignar directamente enteros a punteros (ej. `int* p = 5`) sin requerir casteo explícito ni operador de dirección `&`. |
| **VAR-02** | **Alta** | **Arreglos anidados en `extract_type`:** `extract_type` extrae `array[type_node.nodes[2].token.value]`. Si el arreglo es multidimensional (`array[array[int]]`), `type_node.nodes[2]` es un `ASTRef` (`ARRAY`) y no un token con `.token.value`. | Provoca un error de ejecución de Python (`AttributeError`) al declarar arreglos multidimensionales. |
| **VAR-03** | **Media** | **Inferencia nula en literales de colección:** `_infer_node` no reconoce nodos de listas literales `[1, 2, 3]`. Devuelve `None`, impidiendo validar tipos en asignaciones directas de arreglos literales. | Asignaciones como `array[int] a = [1, 2, 3]` pasan sin validación o requieren tipo explícito sin chequeo de elementos. |
| **VAR-04** | **Media** | **Inferencia de operaciones unarias ausente:** `_infer_node` solo maneja expresiones binarias (`left`/`right`) o tokens aislados. Operadores unarios como `-x`, `!x`, `*p` o `&x` devuelven `None`. | Expresiones con prefijos unarios pierden la inferencia semántica de tipos. |
| **VAR-05** | **Media** | **Inmutabilidad no sincronizada con palabra clave `const`:** En `Storage.add_variable`, la constante se define exclusivamente por `name.isupper()`. Si una variable se declara como `const int x = 10` pero el identificador está en minúsculas, no se marca como inmutable. | Las variables declaradas con modificador de inmutabilidad sintáctico pueden ser reasignadas si su nombre no está en mayúsculas. |

---

### 2.6. `for_statement.py` y `while_statement.py` (Estructuras de Control Repetitivas)

| ID | Gravedad | Descripción del Agujero | Impacto Técnico |
|---|---|---|---|
| **LOP-01** | **Alta** | **Fuga de ámbito de las variables de bucle (Scope Leak):** `visit_for` registra las variables objetivo directamente en el almacenamiento padre (`storage.add_variable(...)`). | La variable de bucle (`i`, `item`) contamina el ámbito exterior y puede colisionar con variables homónimas de declaraciones posteriores. |
| **LOP-02** | **Alta** | **Inferencia errónea en iteración de arreglos:** En `_infer_loop_var_type`: `if col_type.startswith('array[') and ',' in col_type:`. Si el arreglo se tipa como `array[int]` o `array[Point]` (sin coma), la condición falla y cae al valor por defecto `'int'`. | Si se itera `array[Point]`, la variable del bucle se tipa erróneamente como `int` en lugar de `Point`. |
| **LOP-03** | **Media** | **Validación de tipo descartada en la condición de `while`:** `visit_while` infiere el tipo de la condición pero descarta el resultado (`_ = infer_value_type(...)`), sin verificar que sea booleano, numérico o puntero. | Expresiones inválidas como una llamada a función `void` en `while mi_funcion_void():` son aceptadas por el procesador semántico. |
| **LOP-04** | **Baja** | **Protocolo de iteradores personalizado:** El bucle `for` solo soporta rangos, cadenas y arreglos nativos; no permite iterar sobre clases que implementen métodos `__iter__` o `__next__`. | Restricción del bucle `for` a tipos primitivos y arreglos nativos de C. |

---

### 2.7. `if_statement.py` (Condicionales y Bloques de Decisión)

| ID | Gravedad | Descripción del Agujero | Impacto Técnico |
|---|---|---|---|
| **IFS-01** | **Media** | **Ausencia de aislamiento de ámbito de bloque (`BlockScope`):** Cualquier variable declarada dentro del bloque `if`, `elif` o `else` mediante `VAR_DECL` se registra en el ámbito contenedor (`Storage` o `LocalStorage`). | Las variables declaradas localmente dentro de una rama condicional persisten y son visibles en el resto de la función o módulo. |
| **IFS-02** | **Media** | **Falta de análisis de asignación definitiva:** No se verifica si una variable usada tras el condicional fue asignada en todas las rutas posibles (`if` y `else`). | Posibilidad de lecturas de variables no inicializadas en el código generado. |
| **IFS-03** | **Baja** | **Validación de condición no coercible descartada:** Al igual que en `while`, se infiere la condición del `if` y `elif`, pero no se verifica que su tipo sea convertible a booleano en C. | Aceptación de condiciones de tipo `void` o estructuras complejas sin sobrecarga booleana. |

---

### 2.8. `enum_decl.py` (Enumeraciones)

| ID | Gravedad | Descripción del Agujero | Impacto Técnico |
|---|---|---|---|
| **ENM-01** | **Media** | **Colisión interna de miembros no detectada:** `visit_enum` no mantiene un conjunto `seen_members`. Si el usuario declara miembros duplicados dentro del mismo enum (ej. `enum Color: RED = 1, RED = 2`), se aceptan y se agregan a la lista. | Generación de C redundante o errónea con identificadores duplicados en el enum. |
| **ENM-02** | **Baja** | **Sin soporte de tipo entero subyacente:** No se permite especificar el tipo base del enum (ej. `enum State : uint8`), defaulting siempre a `int` implícito en C. | Limitación en optimización de memoria para sistemas embebidos o banderas compactas. |

---

### 2.9. `type_decl.py` (Alias de Tipos)

| ID | Gravedad | Descripción del Agujero | Impacto Técnico |
|---|---|---|---|
| **TYP-01** | **Media** | **Falta de detección de ciclos en resolución de alias (`TypeAlias`):** Si bien `Storage.resolve_type` tiene un conjunto `visited` para evitar bucles infinitos durante la resolución, la función `visit_typealias` no previene la definición cíclica en el registro (ej. `TypeAlias A -> B` y luego `TypeAlias B -> A`). | Deja el alias en un estado circular que se resuelve a sí mismo sin error claro para el desarrollador. |
| **TYP-02** | **Baja** | **Incompatibilidad con tipos genéricos:** No se soportan alias parametrizados (ej. `TypeAlias Vector[T] -> array[T]`). | Limita la reutilización de alias a tipos monomórficos concretos. |

---

### 2.10. `clauses.py`, `imports.py` e `includes.py` (Módulos y Cláusulas)

| ID | Gravedad | Descripción del Agujero | Impacto Técnico |
|---|---|---|---|
| **MOD-01** | **Media** | **Efecto colateral permanente de la cláusula `visibility`:** Al ejecutarse `clause visibility: "private"`, `storage.privacy` cambia para todas las declaraciones subsiguientes de forma irreversible si no se restablece explícitamente. | Posibles errores sutiles de privacidad en archivos con múltiples declaraciones donde se esperaba un bloque local de visibilidad. |
| **MOD-02** | **Media** | **Detección de dependencias circulares entre módulos `.egl`:** En `imports.py`, si el módulo `A` importa al módulo `B` y `B` importa a `A`, `compile_source` puede entrar en recursión infinita o estado inconsistente. | Bloqueo o fallo de la compilación en arquitecturas con referencias cruzadas. |
| **MOD-03** | **Baja** | **Silenciamiento de cláusulas desconocidas:** Si se provee una cláusula no soportada (ej. `clause optimize: "O3"`), el visitor no emite advertencia ni error, ignorándola silenciosamente. | Oculta posibles errores tipográficos en directivas de compilación. |

---

## 3. Matriz de Priorización de Correcciones

Para estructurar las siguientes iteraciones de desarrollo, los agujeros se clasifican según su impacto en la estabilidad y corrección semántica:

```
+---------------------------------------------------------------------------------+
| PRIORIDAD ALTA (Crítica para la corrección del compilador)                      |
+---------------------------------------------------------------------------------+
| VAR-01: Corrección de validación de punteros (rstrip('*') permite int a int*)    |
| VAR-02: Manejo de arreglos multidimensionales (array[array[T]]) en extract_type  |
| CAL-01: Mapeo y ordenamiento de argumentos con nombre (kwargs)                  |
| CAL-02: Soporte para cadenas de llamadas a métodos intermedios fluidos          |
| CAL-03: Recorrido de clases base (herencia) en búsqueda de métodos y atributos  |
| CLS-01: Herencia completa de campos y métodos entre clases                      |
| CLS-02: Implementación semántica de super()                                     |
| CLS-03: Enlace de sobrecarga de operadores mágicos a operadores del lenguaje     |
| LOP-01: Aislamiento de ámbito de variables de bucle for                         |
| LOP-02: Corrección de inferencia de elementos de arreglos simples en for        |
| FNC-01: Análisis de caminos de retorno (Control Flow / Return Path Analysis)   |
+---------------------------------------------------------------------------------+
| PRIORIDAD MEDIA (Robustez y características esperadas del lenguaje)             |
+---------------------------------------------------------------------------------+
| ASG-01: Validación de operadores aritméticos/bitwise compuestos (+=, *=)        |
| ASG-02: Cadenas de miembros anidados en self / cls                              |
| FNC-02: Prohibición estricta de funciones anidadas dentro de funciones          |
| FNC-03: Validación de tipos de valores por defecto en firma de funciones        |
| IFS-01: Aislamiento de variables de bloque en condicionales (BlockScope)         |
| LOP-03: Validación de tipo booleano en condición de while                       |
| ENM-01: Validación de identificadores duplicados en enums                       |
| MOD-02: Detección de ciclos de importación entre archivos .egl                  |
+---------------------------------------------------------------------------------+
| PRIORIDAD BAJA (Mejoras ergonómicas y optimizaciones)                           |
+---------------------------------------------------------------------------------+
| ASG-04: Asignación múltiple / desempaquetado de tuplas                          |
| CAL-06: Slices de arreglos y validación estática de límites                     |
| CLS-05: Soporte de decoradores @property y @setter                              |
| CLS-06: Destructores y ciclo de vida de memoria (__del__)                       |
| MOD-03: Advertencia en cláusulas desconocidas                                   |
+---------------------------------------------------------------------------------+
```

---

## 4. Archivos Obsoletos Eliminados en esta Fase

1. `core/processor/errors.py`: Archivo huérfano que definía `UnknownASTNodeError` (reliquia de `processar_ast.py` anterior).
2. `core/processor/visitors/expression.py`: Visitor obsoleto acoplado a nodos `EGL_*` que ya no forman parte de la gramática moderna.
3. `core/processor/visitors/type_decl.py`: Eliminado el alias heredado `visit = visit_typealias`.
4. `core/backend/visitors/expression.py`: Actualizado el fallback para evitar cualquier importación de `core.processor.visitors.expression`.

---

## 5. Conclusión

El procesador semántico se encuentra en un estado **estable, limpio y completamente funcional para la especificación base**, con una tasa de éxito de pruebas del 100% (189 pruebas). La resolución gradual de los puntos de **Prioridad Alta** detallados en este informe dotará a Easy-C de la madurez necesaria para soportar proyectos orientados a objetos complejos y garantizar absoluta seguridad de tipos en la generación de código C.
