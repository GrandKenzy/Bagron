# Frontend y Gramatica

El frontend de Easy-C (EGL) es responsable de la transformacion del codigo fuente en texto plano a una representacion intermedia estructurada en memoria: el arbol de sintaxis abstracta (`ASTProgram`). Este proceso es ejecutado por el framework `gram`, el cual implementa un analizador lexico parametrizable y un motor de reglas sintacticas combinatorias sin dependencia de generadores externos.

---

## Especificacion Tecnica

El punto de entrada del frontend se encuentra en `core/grammar.py`, el cual compone las reglas semanticas definidas en el paquete `core/initiator/rules`.

### Componentes del Motor Sintactico

1. **Tokens y Palabras Clave (`core/initiator/keywords.py`):**
   * Define los conjuntos normativos del lenguaje: `KEYWORDS`, `TYPES`, `BLOCKS`, `SYSTEM_TYPES` y `CLAUSES`.
   * Los identificadores son clasificados por el lexer segun las enumeraciones de `gram.Token` (`IDENT`, `KEYWORD`, `NUMBER`, `STRING`, `CHAR`, `BOOL`, `SYMBOL`).
2. **Definicion de Reglas (`core/initiator/rules/`):**
   * Cada archivo exporta reglas declarativas basadas en los combinadores de `gram`:
     * `gram.Seq`: Secuencia estricta de elementos.
     * `gram.Alt`: Alternativas mutuamente excluyentes (orden de precedencia).
     * `gram.Opt`: Elemento opcional (cero o una ocurrencia).
     * `gram.Many`: Repeticion indefinida (cero o mas ocurrencias).
     * `gram.Some`: Repeticion requerida (una o mas ocurrencias).
     * `gram.Ref`: Referencia perezosa a otra regla para evitar dependencias circulares o permitir recursividad.

### Catalogo de Reglas Sintacticas

| Regla | Archivo Fuente | Nodos Emitidos | Descripcion |
| :--- | :--- | :--- | :--- |
| `EGL_TYPE_SPEC` | `core/initiator/rules/type_spec.py` | `EGL_TYPE_SPEC` | Tipos simples, punteros (`*`) y genericos con argumentos (`array[int, 10]`). |
| `EGL_VAR_DECL` | `core/initiator/rules/var_decl.py` | `EGL_VAR_DECL` | Declaracion de variables con tipado opcional/obligatorio e inicializador. |
| `EGL_FUNC_DECL` | `core/initiator/rules/func_decl.py` | `EGL_FUNC_DECL` | Cabeceras de funcion con tipo de retorno, modificadores (`public`, `private`, `__inline__`), parametros tipados y bloque indentado. |
| `EGL_CLASS_DECL` | `core/initiator/rules/class_decl.py` | `EGL_CLASS_DECL` | Declaraciones de clases con soporte de visibilidad y cuerpo indentado. |
| `EGL_TYPE_DECL` | `core/initiator/rules/type_decl.py` | `EGL_TYPE_DECL` | Definicion de alias o estructuras con palabra clave `struct Type <nombre>:`. |
| `EGL_CALL` | `core/initiator/rules/call.py` | `EGL_CALL`, `EGL_METHOD_CALL` | Invocacion directa `func(args)` o cualificada por namespace/metodo `obj.metodo(args)`. |
| `EGL_EXPRESSION` | `core/initiator/rules/expression.py` | `EGL_EXPRESSION`, `EGL_ADDITIVE`, etc. | Jerarquia completa de operadores matematicos, logicos, relacionales y de bits con precedencia estricta. |
| `EGL_IMPORTS` | `core/initiator/rules/imports.py` | `EGL_IMPORT`, `EGL_INCLUDE`, `EGL_CLAUSE`, `EGL_OBJECT` | Directivas modulares, inclusiones externas y clausulas de entorno. |

---

## Estructura de los Nodos AST

El arbol retornado por `gram.process(grammar, source)` consta de una raiz `ASTProgram` compuesta por nodos `ASTNode`.

### Anatomia de un `ASTNode`

* `node.name` (`str`): Identificador de la regla sintactica que genero el nodo (ej. `'EGL_FUNC_DECL'`).
* `node.level` (`int`): Nivel de indentacion relativo dentro de la jerarquia de bloques.
* `node.tokens` (`list[TokenType]`): Lista de objetos de token inmediatos consumidos directamente por esta regla. Cada token almacena `t.token` y `t.value`.
* `node.children` (`list[ASTNode]`): Nodos hijos que representan subreglas anidadas (ej. parametros o sentencias dentro del cuerpo de una funcion).
* `node.values` (`list[Any]`): Propiedad de solo lectura que calcula y extrae de forma dinamica los valores semanticos literales e identificadores a partir de `tokens` y `children`.

### Consideracion Critica: Mutabilidad en Nodos AST

La propiedad `values` de `ASTNode` es dinamica y carece de setter directo. Para reescribir simbolos durante las fases de mangling o transformacion de llamadas, los colaboradores **deben mutar la propiedad `value` de los tokens en `node.tokens`**:

```python
# Modificacion correcta de un simbolo en el AST
token = node.tokens[1]
token.value = "inmodule_miModulo_miFuncion"
```

---

## Ejemplo de Parseo

Para la siguiente declaracion en codigo EGL:

```easy-c
int duplicar(int valor):
    return valor * 2
```

El frontend genera una jerarquia de nodos equivalente a:

```
ASTProgram
└── EGL_FUNC_DECL [values: ['int', Identifier('duplicar')]]
    ├── EGL_PARAMS
    │   └── EGL_PARAM [values: [Identifier('valor')]]
    │       └── EGL_TYPE_SPEC [values: ['int']]
    └── EGL_FUNC_BODY
        └── EGL_RETURN [values: ['return']]
            └── EGL_VALUE [values: [Identifier('valor'), 2]]
```
