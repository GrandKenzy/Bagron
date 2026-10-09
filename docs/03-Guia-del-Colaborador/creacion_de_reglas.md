# Guia de Creacion de Nuevas Reglas y Caracteristicas

Esta guia proporciona el procedimiento estructurado paso a paso para extender Easy-C (EGL) con nuevas construcciones de lenguaje (por ejemplo, nuevas sentencias de control, operadores o tipos de datos), abarcando desde la gramatica formal hasta la generacion de codigo en el backend C.

---

## Procedimiento Paso a Paso

El desarrollo de cualquier nueva caracteristica atraviesa seis fases secuenciales:

```
[1. Palabras Clave] ──> [2. Regla Sintactica] ──> [3. Gramatica Global]
(keywords.py)          (rules/*.py)             (grammar.py)
      │
      ▼
[4. Objeto Semantico] ─> [5. Procesador AST]  ──> [6. Emision en C]
(objects/*.py)         (processar_ast.py)       (backend/c/visitors)
```

---

### Paso 1: Registrar Palabras Clave (`core/initiator/keywords.py`)
Si la construccion introduce una palabra reservada (ej. `while` o `switch`), se debe añadir al grupo correspondiente en `KEYWORDS`:

```python
KEYWORDS = {
    ...
    'control': ['if', 'else', 'for', 'while'],
    ...
}
```

### Paso 2: Crear la Regla Gramatical (`core/initiator/rules/`)
Definir la regla BNF utilizando los combinadores del framework `gram`:

```python
import gram

EGL_WHILE = gram.Rule(
    'EGL_WHILE',
    gram.Seq(
        'while',
        gram.Ref('EGL_EXPRESSION'),
        ':',
        gram.Ref('EGL_BLOCK')
    )
)
```

### Paso 3: Integrar en la Gramatica Global (`core/grammar.py`)
Incorporar la nueva regla dentro de `EGL_STATEMENT` para que sea reconocida en el cuerpo de funciones o a nivel de raiz:

```python
EGL_STATEMENT = gram.Rule(
    'EGL_STATEMENT',
    gram.Alt(
        EGL_VAR_DECL,
        EGL_WHILE,
        EGL_IF_STATEMENT,
        ...
    )
)
```

### Paso 4: Crear el Objeto Semantico (`core/processor/objects/`)
Crear una clase de modelo que herede de `core.processor.objects.base.Object` para encapsular la estructura en memoria:

```python
from core.processor.objects.base import Object

class WhileStatement(Object):
    def __init__(self, condition, body):
        super().__init__()
        self.condition = condition
        self.body = body
        self.compiled = ''
```

Exportar la clase en `core/processor/objects/__init__.py`.

### Paso 5: Implementar el Visitante Semantico (`core/processor/visitors/`)
1. Crear `core/processor/visitors/while_statement.py`:
   ```python
   import gram
   from core.processor.objects import WhileStatement

   def visit(node: gram.ASTNode) -> WhileStatement:
       condicion = node.children[0].values[0]
       cuerpo = ...
       return WhileStatement(condicion, cuerpo)
   ```
2. Enlazar la llamada en el bucle principal de `core/processor/processar_ast.py`:
   ```python
   elif node.name in ('EGL_WHILE', 'while'):
       while_statement.visit(node)
   ```

### Paso 6: Implementar la Emision en el Backend C (`core/backend/c/`)
1. Crear el emisor en `core/backend/c/visitors/while_statement.py`:
   ```python
   from core.processor.objects import WhileStatement
   from core.backend.c.visitors.expression import format_expression

   def visit(item: WhileStatement, block = None):
       cond_c = format_expression(item.condition, block)
       cuerpo_c = ...
       item.compiled = f"while ({cond_c}) {{\n    {cuerpo_c}\n}}"
   ```
2. Despachar la instancia en `core/backend/c/__init__.py`:
   ```python
   elif isinstance(item, WhileStatement):
       while_statement.visit(item, block)
   ```

---

## Verificacion de Integracion

Una vez completadas las fases, crear un archivo de prueba en `source/main.egl` que utilice la nueva sintaxis y compilar:

```powershell
python egl.py compile source -o program.c --run
```

Comprobar que:
1. El archivo `program.c` contenga la sintaxis C equivalente correcta.
2. GCC compile el archivo sin advertencias ni errores de sintaxis.
3. La ejecucion del binario produzca el resultado previsto.
