# Frontend EasyC (EC)

Especificacion tecnica del frontend para el lenguaje EasyC (.ec / .egl) en el compilador EGL. Analiza codigo basado en indentacion y emite un arbol de sintaxis abstracta (AST) tipado mediante combinadores de Gram.

---

## Modos De Operacion Y Sesion

El analizador opera mediante la sesion dedicada `EASY_C_SESSION`:

- **Aislamiento lexico:** Configurado bajo `Session("Session From Easy C", 'Many')`.
- **Comentarios:** Configurado con punto y coma `;` para comentarios de linea (`config.LEXER_COMMENT_TOKEN = ';'`).
- **Docstrings:** Habilitado el soporte para cadenas de documentacion (`config.LEXER_SUPPORT_DOCSTRINGS = True`).
- **Indentacion:** El lexer emite tokens formales `INDENT` y `DEDENT` para estructurar bloques de codigo sin llaves.
- **Simbolos desactivados:** Deshabilita `**` en `tokens.disabled_symbol('**')`.
- **Migracion:** Ejecuta `EASY_C_SESSION.migrate()` para registrar el estado de la sesion.

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
- **Tipos intrinsecos:** int, int8, int16, int32, int64, uint, uint8, uint16, uint32, uint64, wsize, byte, float, double, middle, char, bool, void, chain, ptr, cptr.
- **Arrays tipados (`ARRAY`):** `array[tipo, tamano]`.
- **Tipo general (`TYPE`):** Alternativa entre array, tipo base o identificador definido por el usuario.
- **Punteros (`POINTER`):** Cadena de asteriscos `*`.
- **Alias (`ALIAS`):** `as identificador`.
- **Parametros (`PAIR_PARAM`):** `[const] ident [*] : tipo [= valor]`.
- **Parametros agrupados (`PARAMETERS`):** Parentesis con lista de parametros separados por comas.
- **Argumentos (`ARGUMENTS`):** Lista de expresiones entre parentesis para invocaciones.
- **Retorno (`RETURN`):** `return [valor]`.

### call.py (Llamadas)
- **Llamada (`CALL`):** `ident(argumentos)`.

### var_decl.py (Declaraciones De Variables)
- **Declaracion con asignacion (`VAR_DECLARATION`):** `[const] ident [*] : tipo = valor`.
- **Declaracion de tipo (`VAR_INITIALIZATION`):** `[const] ident [*] : tipo`.
- **Variable raiz (`VAR`):** `[privacy] (VAR_DECLARATION | VAR_INITIALIZATION)`.
- **Asignacion (`VAR_ASSIGNATION`):** `ident operador valor` (`=`, `+=`, `-=`, `*=`, `/=`, `%=`, `&=`, `|=`, `^=`, `<<=`, `>>=`).

### func_decl.py (Declaracion De Funciones)
- **Decoradores (`DECORATORS`):** `@ident`.
- **Firma (`FUNCTION_SIGNATURE`):** `[privacy] [inline] tipo ident(parametros):`.
- **Cuerpo (`FUNCTION_BODY`):** Bloque indentado `INDENT ... DEDENT` conteniendo estructuras, condicionales, bucles, llamadas, variables, retornos o `pass`.
- **Funcion completa (`FUNCTION`):** `[DECORATORS] FUNCTION_SIGNATURE FUNCTION_BODY`.

### struct_decl.py (Estructuras, Moldes Y Flags)
- **Alineacion (`ALIGNEMENT`):** `__align__ (numero | tipo)`.
- **Atributos (`ATTRIBUTES`):** Lista de modificadores `ALIGNEMENT` o `__packed__`.
- **Estructura (`STRUCT`):** `[privacy] [volatile] struct ident: INDENT [ATTRIBUTES] miembros DEDENT`.
- **Molde (`MOLD`):** `[privacy] [volatile] mold ident: INDENT [ATTRIBUTES] miembros DEDENT`.
- **Campos de bits (`FLAGS`):** `[privacy] [volatile] flags ident: INDENT [ATTRIBUTES] miembros_con_tamano DEDENT`, donde cada campo define ancho de bits mediante `_N`.

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
- **Bucle For (`FOR`):** `for (identificadores) iterador (valores): cuerpo`. Soporta iteradores `in`, `ran`, `iter`, `index` y desempaquetado de tuplas.
- **Cuerpo de sentencia (`STATEMENT_BODY`):** Bloque delimitado por `INDENT ... DEDENT`.

### imports.py (Modulos E Inclusiones)
- **Importacion modular (`IMPORT`):**
  - `import { a, b as B } from modulo`
  - `import modulo [as alias]`
- **Inclusion foranea (`INCLUDE`):**
  - `include { a, b as B } from "header.h"`
  - `include "header.h" [as alias]`

---

## Composicion Del AST (core/frontend/EASYC/__init__.py)

- **Expresiones duales (`DUEXPR`):** `DualExpr` con identificadores, llamadas, numeros, cadenas, booleanos y `Null`.
- **Enlace de `VALUE`:** `VALUE.entrypoint = Alt(DUEXPR, CALL, BOOL, NULL, IDENT, STRING, NUMBER, DOCSTRING)`.
- **Punto de entrada (`ENTRYPOINT`):** Alternativa principal conectada a `EASY_C_SESSION.entrypoint` que resuelve declaraciones a nivel de archivo.

---

## Flujo En El Compilador

El compilador recibe un archivo `.ec` en `core/compiler/control.py`.
Se activa la sesion mediante `EASYC.EASY_C_SESSION.load()`.
Se ejecuta el tokenizador con soporte de indentacion: `TKNS = EASYC.EASY_C_SESSION.tokenize(content, path.name)`.
El parser genera el AST y retorna codigo de lenguaje `1` (`LANG == 1`).
 En `core/compiler/__init__.py`, se invoca `core.frontend.EASYC.processor.process(self, AST)`.
El procesador valida las clausulas del entorno (`storage.define_clause`) y extrae las definiciones semanticas mediante `core/frontend/EASYC/tools/`.
