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

### prep.py (Bloques Raw De Ensamblador)
- **Cabecera:** `#prep assembler "dialecto"`.
- **Cierre:** `#end`.
- **Ubicacion:** únicamente dentro del cuerpo de una función.
- **Primera fase:** el preprocesador extrae el contenido sin tokenizarlo y lo
  expande y escribe en `build/prep/<modulo>/<funcion>__prep_<indice>.asm`.
  En Windows x64, `{parametro}` se sustituye por su operando ABI según el ancho declarado y los parámetros posteriores al cuarto usan el stack ABI. Se soportan `intel` y `att`; el archivo
  se ensambla a `.obj` para enlazarlo con LLVM. El retorno usa `return asm` y
  `EAX`.

### func_decl.py (Declaracion De Funciones)
- **Decoradores (`DECORATORS`):** `@ident`.
- **Firma (`FUNCTION_SIGNATURE`):** `[privacy] [inline] func ident(parametros) tipo [*]:`.
- **Cuerpo (`FUNCTION_BODY`):** Bloque indentado `INDENT ... DEDENT` conteniendo estructuras, condicionales, bucles, llamadas, variables, retornos o `pass`.
- **Funcion completa (`FUNCTION`):** `[DECORATORS] FUNCTION_SIGNATURE FUNCTION_BODY`.
- **Scope semantico:** Cada funcion top-level crea un `Storage` propio para sus parametros y variables locales. El scope resuelve primero sus simbolos y despues el Storage global.
- **Estado actual:** Las funciones enteras pueden retornar literales, parametros,
  variables locales, operaciones aritmeticas y llamadas a otras funciones
  enteras. Las funciones `void` pueden terminar con `return` vacio y sus
  llamadas solo pueden usarse como sentencias. Las variables locales admiten
  declaracion, inicializacion y asignacion con comprobacion de tipos. Los
  metodos de clases, valores por defecto de parametros y expresiones complejas
  quedan para fases posteriores.
- **Decorador `@assembler`:** habilita un único bloque `#prep assembler
  "dialecto"` opcional y un único `return`; cualquier otra sentencia se
  rechaza. Los nombres de parámetros son el contrato de la plantilla y no se agregan anotaciones `in`, `out` o `inout`.
- **Decorador `@unsafe`:** habilita la frontera insegura de una función. Las
  funciones seguras no pueden llamar funciones `@unsafe`, desreferenciar
  punteros de procedencia desconocida ni usar índices dinámicos de arrays.
  `@assembler` implica `@unsafe`.
- **Punto de entrada:** Todo modulo ejecutable debe declarar `func main() int:` con una expresion entera emitible; una funcion `main` dentro de una clase no satisface este requisito.

### struct_decl.py (Estructuras, Moldes Y Flags)
- **Alineacion (`ALIGNEMENT`):** `__align__ (numero | tipo)`.
- **Decoradores de agregado (`AGGREGATE_DECORATORS`):** `@packed`,
  `@order_lsb` o `@order_msb` antes de una declaración. Los decoradores de
  orden solo aplican a `flags`.
- **Atributos (`ATTRIBUTES`):** Lista de modificadores `ALIGNEMENT`.
- **Estructura (`STRUCT`):** `[decoradores] [privacy] [volatile] struct ident: INDENT [ATTRIBUTES] miembros DEDENT`.
- **Molde (`MOLD`):** `[decoradores] [privacy] [volatile] mold ident: INDENT [ATTRIBUTES] miembros DEDENT`.
- **Campos de bits (`FLAGS`):** `[decoradores] [privacy] [volatile] flags ident tipo_base: INDENT [ATTRIBUTES] miembros DEDENT`, donde `tipo_base` es un entero fijo y cada campo usa `nombre: tipo = literal`.

La fase semantica registra los tres como tipos nominales en un registro separado
del namespace de variables y funciones. Conserva los campos como `FieldSpec`,
valida nombres y tipos, rechaza agregados vacíos y ciclos por valor, y asigna
offsets de bits a cada campo de `flags`. Un `flags` requiere una base entera
explícita de 8, 16, 32 o 64 bits y no puede excederla.

El backend emite `struct` como campos ordenados, `mold` como almacenamiento
compartido de tamaño máximo y `flags` como un único entero de respaldo. Los
accesos a miembros, asignaciones y asignaciones compuestas se emiten a LLVM;
los campos de `flags` hacen read-modify-write con máscaras. `@packed`,
`volatile` y `__align__` participan en el layout y las operaciones de memoria.
Un campo de `flags` es asignable pero no direccionable, y una vista puntero de
`mold` solo puede desreferenciarse desde una función `@unsafe`.

### enum_decl.py (Enumeraciones)
- **Elemento (`ENUM_ITEM`):** `ident [= numero],`.
- **Cuerpo (`ENUM_BODY`):** Bloque indentado con elementos o `pass`.
- **Declaracion (`ENUM`):** `[privacy] enum ident [tipo_entero]: ENUM_BODY`.

Los enums usan `int32` por defecto, o el tipo entero escalar indicado despues
del nombre, por ejemplo `enum Estado int8:`. El primer miembro implicito vale
`0`; cada miembro posterior incrementa el valor anterior y un valor explicito
reinicia la secuencia. Los valores se validan contra el rango del tipo base.
La sintaxis actual exige coma despues de cada miembro, incluso el ultimo. Los
valores numericos repetidos son validos, pero los nombres no.

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
- **Bucle For (`FOR`):** `for identificador: tipo ran (inicio, limite, paso): cuerpo`. El limite final es exclusivo, el iterador debe tener un tipo entero explicito y `step` no puede ser cero. Esta es la unica forma de iteracion numerica; `while` permanece como bucle condicional independiente.
- **Cuerpo de sentencia (`STATEMENT_BODY`):** Bloque delimitado por `INDENT ... DEDENT`.

### imports.py (Modulos Bagron)
- **Importacion modular (`IMPORT`):**
  - `import { a, b as B } from modulo`
  - `import modulo [as alias]`
- **Resolucion:** los nombres se resuelven como archivos `.bg` relativos al
  modulo actual, al proyecto y a `lib/` o `libs/`; se detectan ciclos.

### includes.py (Dependencias Nativas)
- **Declaracion (`INCLUDE`):** `include "header" link "library"`.
- **Resolucion:** `windows` se normaliza a `windows.h` y `kernel32` a la
  biblioteca nativa correspondiente; el header se valida con `clang` y la
  biblioteca se propaga al enlazador LLVM.

### externs.py (Firmas ABI Nativas)
- **Declaracion (`EXTERN`):** `extern "library":` seguido de firmas sin cuerpo.
- **Firma:** `Nombre(parametro: tipo, ...) tipo`; los retornos puntero usan
  `Nombre(...) *: tipo`, como en `GetStdHandle(...) *: void`.
- **Frontera de seguridad:** una función `extern` es insegura por defecto y
  debe llamarse desde una función `@unsafe`.

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
Primero registra todos los nombres de tipos top-level (`enum`, `struct`,
`mold` y `flags`); despues valida sus miembros y campos. Esto permite que un
campo nombre otro tipo declarado mas adelante en el mismo modulo.
