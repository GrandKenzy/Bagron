# Reporte Técnico de Auditoría: Brechas y "Agujeros" en los Visitores Semánticos

**Fecha:** Octubre 2026  
**Ubicación:** `core/processor/`  
**Estado de Pruebas Unitarias:** 189/189 exitosas (100% verde)

---

## 1. Resumen Ejecutivo

El procesador semántico de Easy-C (`core/processor`) ha culminado exitosamente la transición hacia una arquitectura moderna basada en el AST de **Gram** (`gram.ast.ASTRef`), desacoplada completamente del antiguo AST sintáctico (`EGL_*`). La limpieza arquitectónica eliminó archivos obsoletos (`errors.py`, `visitors/expression.py`, y alias de retrocompatibilidad), consolidando un pipeline directo y fuertemente tipado.

Sin embargo, a medida que el lenguaje escala hacia soporte completo de estructuras avanzadas, orientación a objetos y optimización para el backend de C, se han identificado **agujeros semánticos**, casos de borde no manejados y oportunidades de robustecimiento en los visitores actuales (`core/processor/visitors/`).

Este documento cataloga de forma exhaustiva y detallada cada una de estas brechas técnicas para guiar las próximas fases de desarrollo.

---

## 2. Auditoría Detallada por Visitor

### 2.1. `assign.py` (Asignaciones y Operadores Compuestos)

| ID | Gravedad | Descripción del Agujero | Impacto Técnico |
|---|---|---|---|
| **ASG-01** | **Alta** | **Falta de validación de tipos en operadores compuestos (`+=`, `-=`, `*=`, etc.):** El visitor extrae el operador `op`, pero solo valida que el valor asignado sea compatible con el tipo destino (`validate_type`), sin comprobar si el operador aritmético/bitwise está permitido para ese tipo. | Permite operaciones inválidas en tiempo semántico como `str += 5`, `bool *= 2` o `Point += 1` sin emitir un error de tipos en el procesador. |
| **ASG-02** | **Media** | **Cadenas de miembros en clases limitadas a 1 nivel (`items[1]`):** En asignaciones a través de `self`, `cls` o nombre de clase, el visitor únicamente extrae `items[1]`. | No soporta asignaciones a estructuras anidadas dentro de una instancia o clase, tales como `self.config.timeout = 10` o `MyClass.sub.val = 5`. |
| **ASG-03** | **Media** | **Ausencia de sobrecarga de operadores de asignación (`__iadd__`, etc.):** Si una clase define métodos para sobrecarga de operadores en sitio, el visitor los trata como asignaciones primitivas de C. | Imposibilidad de sobrecargar operadores compuestos en clases de usuario. |
| **ASG-04** | **Baja** | **Sin soporte de asignación múltiple / desempaquetado de tuplas:** La gramática y el visitor solo admiten un único `target` (`ASSIGN_TARGET`). | Patrones idiomáticos modernos como `a, b = x, y` generan error de sintaxis en lugar de desempaquetado. |
| **ASG-05** | **Media** | **Inmutabilidad superficial en punteros y estructuras `const`:** Se verifica `is_constant` en la raíz de la variable, pero no se distingue semánticamente entre `const T*` (puntero a dato constante) y `T* const` (puntero constante a dato mutable). | Asignar a `p.data[0] = 5` o `*p = 10` cuando el valor apuntado es constante no dispara error si el puntero no es constante. |

---

### 2.2. `call.py` (Llamadas a Funciones, Métodos, Cadenas y Acceso a Índices)

| ID | Gravedad | Descripción del Agujero | Impacto Técnico |
|---|---|---|---|
| **CAL-01** | **Alta** | **Argumentos con nombre (`kwargs`) no vinculados:** `extract_call_args` extrae `kw_args`, pero en `visit_call`, `_validate_method_arguments` y `_instantiate_class`, la validación de parámetros se realiza estrictamente posicional (`zip(params, args)`). | Llamar a una función o método con argumentos con nombre (ej. `func(b=10, a=20)`) ignora los kwargs en la validación semántica y no reordena los argumentos para el backend. |
| **CAL-02** | **Alta** | **Llamadas a métodos encadenados intermedios ("Fluent Interface"):** En `visit_member_chain`, la función asume que solo el *último* nodo puede ser una llamada (`CALL`). Si un nodo intermedio es una llamada (ej. `builder.step1().step2()` o `get_player().get_pos().x`), `target_parts` intenta leer `.token.value` sobre un `ASTRef` de tipo `CALL`. | Falla con excepción de atributo o genera una representación corrupta al procesar patrones fluidos o llamadas anidadas. |
| **CAL-03** | **Alta** | **Resolución de métodos sin recorrido de clases base (Herencia ausente en dispatch):** Al validar `instance_methods`, `class_methods` o `static_methods` en una clase, únicamente se consultan los diccionarios locales de esa clase. No se recorre la lista `class_obj.bases`. | Llamar a un método heredado (`child.metodo_padre()`) lanza erróneamente `AttributeError: La clase 'Child' no tiene un método...`. |
| **CAL-04** | **Media** | **Argumentos variádicos (`*args`) sin tipado ni empaquetado:** Se permite `len(args) >= min_args` si existe un parámetro variádico, pero no se valida el tipo de los argumentos sobrantes ni su conversión a tupla/lista en el backend. | Pérdida de seguridad de tipos en funciones variádicas. |
| **CAL-05** | **Media** | **Referencias hacia adelante (Forward References / Recursión mutua):** El procesador evalúa llamadas en una sola pasada secuencial. Si la función `A` invoca a la función `B`, y `B` está definida más adelante en el mismo archivo, `storage.resolve('B')` no la encuentra y falla como no declarada. | Obliga al usuario a ordenar funciones de manera ascendente estricta; impide recursión mutua sin pre-declaración explícita. |
| **CAL-06** | **Baja** | **Indexación sin validación de rangos ni soporte de slices:** `visit_index_access` valida que el índice sea entero, pero no evalúa límites estáticos conocidos ni soporta sintaxis de rebanado (`arr[start:end]`). | Índices fuera de rango en arreglos de tamaño constante pasan al compilador de C; falta de rebanado nativo. |

---

### 2.3. `class_decl.py` (Declaración y Semántica de Clases)

| ID | Gravedad | Descripción del Agujero | Impacto Técnico |
|---|---|---|---|
| **CLS-01** | **Alta** | **Herencia incompleta / Sin resolución de MRO:** `CLASS_HERENCY` recopila las clases base en `class_obj.bases`, pero no copia ni hereda campos de instancia, atributos de clase ni métodos. | Las subclases no heredan el estado ni el comportamiento de sus clases base. |
| **CLS-02** | **Alta** | **Sin soporte de `super()`:** No existe palabra clave ni función mágica `super()` para delegar la inicialización en constructores padre (`super().__init__()`) o invocar métodos sobreescritos. | Dificulta la inicialización jerárquica de structs e instancias. |
| **CLS-03** | **Alta** | **Sobrecarga de operadores no vinculada:** Las funciones mágicas `__add__`, `__sub__`, `__mul__`, `__eq__`, `__getitem__`, `__setitem__`, `__str__` pueden ser declaradas en una clase, pero no están mapeadas a los operadores de Easy-C ni a su traducción a funciones C (`Clase_add(a, b)`). | La sobrecarga de operadores solo funciona mediante llamadas explícitas a métodos. |
| **CLS-04** | **Media** | **Falta de detección de ciclos en herencia:** Si una clase se declara como `class A(B):` y `class B(A):`, el procesador registra ambas sin validar la aciclicidad del grafo de tipos. | Provocaría bucles infinitos en cualquier algoritmo de resolución de herencia futuro. |
| **CLS-05** | **Media** | **Sin propiedades (`@property`, `@setter`):** No se reconocen decoradores de propiedad para exponer métodos como atributos de lectura/escritura. | Todo acceso a miembros computados debe ser una llamada a método explícita. |
| **CLS-06** | **Media** | **Destructores y gestión RAII (`__del__`):** No se modela el ciclo de vida de destrucción. Como Easy-C se compila a C, la ausencia de destructores impide la liberación automática de memoria o de recursos (`free()`, `close()`). | Fugas de memoria potenciales si el usuario no libera manualmente las estructuras instanciadas en el heap. |
| **CLS-07** | **Baja** | **Visibilidad uniforme a nivel de clase:** Todos los métodos y atributos adoptan la visibilidad de la clase (`storage.privacy`). No se pueden marcar métodos individuales como `private` o `public` dentro del bloque de clase. | Falta de encapsulamiento granular dentro de una clase pública. |

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
