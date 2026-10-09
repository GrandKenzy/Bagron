# Procesador Semantico y Sistema de Tipos

El procesador semantico constituye la fase intermedia del compilador. Su responsabilidad es transformar el arbol sintactico heterogeneo (`ASTProgram`) emitido por el frontend en una coleccion tipada y coherente de objetos semanticos de dominio, almacenados en `core/processor/objects`. Asimismo, gestiona la validacion de contratos de tipos y la resolucion de llamadas a librerias.

---

## Especificacion Tecnica

El flujo de procesamiento se inicia mediante `core.processor.process(ast)`, implementado en `core/processor/processar_ast.py`. Este modulo recorre los nodos de nivel superior y delega su analisis en los visitantes especializados del subpaquete `core/processor/visitors/`.

### Registro Global de Objetos (`base.ITEMS`)

Todos los objetos analizados heredan de la clase base `core.processor.objects.base.Object`. Al instanciarse, cada objeto se registra automaticamente en el diccionario global `base.ITEMS`, preservando el orden secuencial de declaracion.

El ciclo de vida del compilador provee funciones de acceso en `core/processor/objects/__init__.py`:
* `get_items()`: Retorna el diccionario `base.ITEMS`.
* `get_vars()`: Filtra y retorna unicamente las instancias de tipo `Variable`.
* `clear()`: Limpia `base.ITEMS` para evitar contaminacion cruzada entre fases de compilacion.

---

## Modelo de Objetos Semanticos

| Objeto | Archivo Fuente | Atributos Principales | Descripcion |
| :--- | :--- | :--- | :--- |
| `Variable` | `objects/variable.py` | `name`, `value`, `type`, `privacity`, `is_constant`, `fixed_size`, `element_type`, `is_pointer`, `pointer_base_type` | Representa variables escalares, punteros, cadenas y arrays de tamaño fijo. |
| `Function` | `objects/function.py` | `name`, `body`, `return_type`, `parameters`, `privacity`, `returned`, `is_inline`, `compiled` | Modela funciones con lista de parametros `FunctionParam`, cuerpo y sentencia de retorno. |
| `FunctionParam` | `objects/function.py` | `type`, `name`, `is_variadic`, `default`, `has_default` | Especificacion de parametros de entrada en una funcion. Soporta indexacion por tupla `(type, name)`. |
| `Returned` | `objects/returned.py` | `value` | Modela la expresion o identificador asociado a la sentencia `return`. |
| `Call` | `objects/call.py` | `name`, `args`, `kwargs`, `returntype`, `is_pointer` | Invocacion directa a funciones de modulo, del sistema o funciones C externas. |
| `MethodCall` | `objects/method_call.py` | `target`, `method`, `args`, `returntype` | Llamada cualificada a traves de namespace (`namespace.simbolo`) o metodos de clase. |
| `Assign` | `objects/assign.py` | `target`, `value` | Asignacion a variables existentes o accesos indexados (`arr[i] = val`). |
| `IfStatement` | `objects/if_statement.py`| `condition`, `body`, `else_body` | Estructuras condicionales con ramas de ejecucion alternativas. |
| `ForStatement` | `objects/for_statement.py`| `variable`, `start`, `end`, `step`, `body` | Bucles iterativos acotados. |
| `TypeDecl` | `objects/type_decl.py` | `name`, `base_type`, `fields`, `modifiers` | Definiciones de tipos de usuario o alias declarados con `struct Type`. |
| `ClassDecl` | `objects/class_decl.py` | `name`, `properties`, `methods`, `privacity` | Declaraciones de clases y colecciones de metodos orientados a objetos. |

---

## Sistema de Tipos (`core/processor/type_system.py`)

El subsistema `type_system.py` normaliza y mapea los identificadores de tipo del lenguaje EGL a sus representaciones correspondientes en el estandar C99/C11.

### Mapeo de Tipos Nativos a C

| Tipo EGL | Tipo C Generado | Formato `printf` | Descripcion |
| :--- | :--- | :--- | :--- |
| `int`, `int64`, `__int64_t__` | `int64_t` | `%lld` | Entero con signo de 64 bits. |
| `int32`, `__int32_t__` | `int32_t` | `%d` | Entero con signo de 32 bits. |
| `int16`, `__int16_t__` | `int16_t` | `%d` | Entero con signo de 16 bits. |
| `int8`, `__int8_t__` | `int8_t` | `%d` | Entero con signo de 8 bits. |
| `uint`, `uint64`, `__uint64_t__` | `uint64_t` | `%llu` | Entero sin signo de 64 bits. |
| `uint32`, `__uint32_t__` | `uint32_t` | `%u` | Entero sin signo de 32 bits. |
| `uint16`, `__uint16_t__` | `uint16_t` | `%u` | Entero sin signo de 16 bits. |
| `uint8`, `__uint8_t__` | `uint8_t` | `%u` | Entero sin signo de 8 bits. |
| `float`, `__float_t__` | `float` | `%f` | Punto flotante de precision simple (32 bits). |
| `double`, `__double_t__` | `double` | `%lf` | Punto flotante de doble precision (64 bits). |
| `middle`, `__middle_t__` | `_Float16` | `%f` (cast double) | Punto flotante de media precision (16 bits). |
| `char`, `__char_t__` | `char` | `%c` | Caracter individual ASCII. |
| `bool`, `boolean` | `bool` | `%s` ("true"/"false") | Booleano estandar (`<stdbool.h>`). |
| `str`, `string` | `char*` | `%s` | Puntero a cadena inmutable terminada en nulo. |
| `ptr`, `pointer`, `__void_p_t__` | `void*` | `%p` | Puntero generico a memoria. |
| `void` | `void` | N/A | Tipo nulo o ausencia de valor. |

### Tipos Genericos y Contenedores

La funcion `resolve_generic_type(base_type, type_args)` resuelve declaraciones con argumentos genericos:

1. **Arrays Fijos:** `array[int, 10]` produce una variable de tipo `array` con `element_type = 'int'` y `fixed_size = 10`, emitiendose en C como `int64_t nombre[10];`.
2. **Cadenas de Longitud Fija:** `chain[32]` o `str[32]` se traduce a un buffer plano en C: `char nombre[32];`.
3. **Punteros Tipados:** Declaraciones del estilo `__void_p_t__ char` o `ptr int` configuran `pointer_base_type`, generando en C punteros explicitos como `char*` o `int64_t*`.

---

## Resolucion de Ambitos y Similitud Tipografica

Durante la visita de variables y funciones en `core/processor/visitors/var_decl.py`, el procesador vincula cada variable con su funcion contenedora mediante `in_scope`.

En caso de referenciar variables no declaradas, el backend C implementa un algoritmo de similitud difusa (`difflib.SequenceMatcher`) en `check_variable_defined` que sugiere nombres similares para facilitar el diagnostico del desarrollador, restringido exclusivamente a identificadores unicos para evitar falsos positivos con expresiones compuestas.
