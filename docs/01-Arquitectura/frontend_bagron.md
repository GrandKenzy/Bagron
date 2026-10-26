# Frontend Bagron

Especificacion tecnica del frontend para el lenguaje Bagron (.bg) en el compilador. Analiza codigo basado en indentacion y emite un arbol de sintaxis abstracta (AST) tipado mediante combinadores de Gram.

---

## Modos De Operacion Y Sesion

El analizador opera mediante la sesion dedicada `BAGRON_SESSION`:

- **Aislamiento lexico:** Configurado bajo `Session("Session From Bagron", 'Many')`.
- **Comentarios:** Configurado con punto y coma `;` para comentarios de linea (`config.LEXER_COMMENT_TOKEN = ';'`). El punto y coma no termina instrucciones Bagron.
- **Docstrings:** Habilitado el soporte para cadenas de documentacion (`config.LEXER_SUPPORT_DOCSTRINGS = True`).
- **Indentacion:** El lexer emite tokens formales `INDENT` y `DEDENT` para estructurar bloques de codigo sin llaves.
- **Simbolos desactivados:** Deshabilita `**` en `tokens.disabled_symbol('**')`.
- **Migracion:** Ejecuta `BAGRON_SESSION.migrate()` para registrar el estado de la sesion.

---

## Catalogo De Reglas Sintacticas (syntax/items/)

### clauses.py (Directivas De Compilador)
- **Regla `CLAUSE`:** `clause <grupo> valor`.
- **Propiedades soportadas:**
  - `Visibility`: public, private.
  - `Arch`: amd, arm, x86.
  - `System`: linux, windows, auto.
  - `Optimizations`: dev, prod, high.
  - `StackLimit`: valor numerico entero.

### value.py (Tipos, Arrays Y Parametros)
- **Tipos intrinsecos:** int, int8, int16, int32, int64, uint, uint8, uint16, uint32, uint64, wsize, byte, float, double, middle, char, bool, void, chain, callptr, Bint<n>, uBint<n>.
- **Enteros de ancho exacto:** `Bint<n>` con signo y `uBint<n>` sin signo; `n` es un ancho literal positivo entre `<` y `>`.
- **Arrays tipados (`TYPE`):** `tipo[]`, con soporte para dimensiones sucesivas como `tipo[][]`.
- **Tipo general (`TYPE`):** Tipo base o identificador definido por el usuario, seguido opcionalmente de sufijos `[]`.
- **Punteros (`POINTER`):** Cadena de asteriscos `*`.
- **Alias (`ALIAS`):** `as identificador`.
- **Declarador (`DECLARATOR`):** `ident [*]` o `const ident *`; el `const` previo al nombre solo califica al puntero.
- **Parametros (`PAIR_PARAM`):** `DECLARATOR : [const] tipo [= valor]`.
- **Parametros agrupados (`PARAMETERS`):** Parentesis con lista de parametros separados por comas.
- **Argumentos (`ARGUMENTS`):** Lista de expresiones entre parentesis para invocaciones.
- **Retorno (`RETURN`):** `return [valor]`.

### call.py (Llamadas)
- **Expresion postfix (`POSTFIX_EXPR`):** `PRIMARY` seguido de cero o mas llamadas, miembros o indices.
- **Llamada (`CALL`):** cualquier `POSTFIX_EXPR` que contenga al menos un sufijo de llamada.

### var_decl.py (Declaraciones De Variables)
- **Declaracion con asignacion (`VAR_DECLARATION`):** `DECLARATOR : [const] tipo = valor`.
- **Declaracion de tipo (`VAR_INITIALIZATION`):** `DECLARATOR : [const] tipo`.
- **Variable raiz (`VAR`):** `[privacy] (VAR_DECLARATION | VAR_INITIALIZATION)`.
- **Asignacion (`VAR_ASSIGNATION`):** `ident operador valor` (`=`, `+=`, `-=`, `*=`, `/=`, `%=`, `&=`, `|=`, `^=`, `<<=`, `>>=`).

### func_decl.py (Declaracion De Funciones)
- **Decoradores (`DECORATORS`):** `@ident`.
- **Firma (`FUNCTION_SIGNATURE`):** `[privacy] [inline] func ident(parametros) tipo [*]:`.
- **Cuerpo (`FUNCTION_BODY`):** Bloque indentado `INDENT ... DEDENT` conteniendo estructuras, condicionales, bucles, llamadas, variables, retornos o `pass`.
- **Funcion completa (`FUNCTION`):** `[DECORATORS] FUNCTION_SIGNATURE FUNCTION_BODY`.

### struct_decl.py (Estructuras, Moldes Y Flags)
- **Alineacion (`ALIGNEMENT`):** `__align__ (numero | tipo)`.
- **Decorador de empaquetado (`PACKED_DECORATOR`):** `@packed` antes de una declaracion `struct`, `mold` o `flags`.
- **Atributos (`ATTRIBUTES`):** Lista de modificadores `ALIGNEMENT`.
- **Estructura (`STRUCT`):** `[@packed] [privacy] [volatile] struct ident: INDENT [ATTRIBUTES] miembros DEDENT`.
- **Molde (`MOLD`):** `[@packed] [privacy] [volatile] mold ident: INDENT [ATTRIBUTES] miembros DEDENT`.
- **Campos de bits (`FLAGS`):** `[@packed] [privacy] [volatile] flags ident: INDENT [ATTRIBUTES] miembros DEDENT`, donde cada campo usa la declaracion tipada con asignacion: `nombre: tipo = valor`.

### enum_decl.py (Enumeraciones)
- **Elemento (`ENUM_ITEM`):** `ident [= numero],`.
- **Cuerpo (`ENUM_BODY`):** Bloque indentado con elementos o `pass`.
- **Declaracion (`ENUM`):** `[privacy] enum ident: ENUM_BODY`.

### class_decl.py (Clases Y Herencia)
- **Herencia (`CLASS_HERENCY`):** `(ident, ...)`.
- **Firma (`CLASS_SIGNATURE`):** `[privacy] class ident [(herencia)]:`.
- **Cuerpo (`CLASS_BODY`):** Bloque indentado con funciones, variables y definiciones internas.
- **Clase completa (`CLASS`):** `[DECORATORS] CLASS_SIGNATURE CLASS_BODY`.

### typealias_decl.py (Alias De Tipo)
- **Declaracion (`TYPEALIAS`):** `[privacy] TypeAlias tipo ident`.

### statements.py (Control De Flujo)
- **Condicion (`CONDITION`):** Evaluacion de regla `VALUE`.
- **Sentencia If (`IF`):** `if condicion: cuerpo` seguido de cero o mas `elif condicion: cuerpo` y un bloque opcional `else: cuerpo`.
- **Bucle While (`WHILE`):** `while condicion: cuerpo`.
- **Bucle For (`FOR`):** `for identificador: tipo ran (inicio, limite, paso): cuerpo`. Esta es la unica forma de iteracion numerica; `while` permanece como bucle condicional independiente.
- **Cuerpo de sentencia (`STATEMENT_BODY`):** Bloque delimitado por `INDENT ... DEDENT`.

### imports.py (Modulos Bagron)
- **Importacion modular (`IMPORT`):**
  - `import { a, b as B } from modulo`
  - `import modulo [as alias]`

---

## Composicion Del AST (core/frontend/__init__.py)

- **Expresiones duales (`DUEXPR`):** `DualExpr` con identificadores, llamadas, numeros, cadenas, booleanos, `Null` y cadenas de acceso.
- **Acceso de miembros (`MEMBER_ACCESS`):** `objeto.campo`, `(puntero).campo` y acceso indexado `array[indice]`.
- **Cadenas de llamada:** `objeto.metodo()(valor).campo[indice]` y llamadas anidadas dentro de argumentos.
- **Desreferenciacion:** una expresion parentizada como `(p)` conserva la forma en el AST para que la fase semantica la interprete segun el tipo.
- **Enlace de `VALUE`:** `VALUE.entrypoint` combina expresiones, llamadas, arrays literales y cadenas postfix.
- **Punto de entrada (`ENTRYPOINT`):** Alternativa principal conectada a `BAGRON_SESSION.entrypoint` que resuelve declaraciones a nivel de archivo.

---

## Flujo En El Compilador

El compilador recibe un archivo `.bg` en `core/compiler/control.py`.
Se activa la sesion mediante `BAGRON.BAGRON_SESSION.load()`.
Se ejecuta el tokenizador con soporte de indentacion: `TKNS = BAGRON.BAGRON_SESSION.tokenize(content, path.name)`.
El parser genera el AST.
En `core/compiler/__init__.py`, se invoca `core.frontend.BAGRON.processor.process(self, AST)`.
El procesador valida las clausulas del entorno (`storage.define_clause`) y extrae las definiciones semanticas mediante `core/frontend/tools/`.
