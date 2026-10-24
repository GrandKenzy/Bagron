# Frontend C

Especificacion tecnica del frontend para lenguaje C en el compilador EGL. Analiza archivos de codigo fuente C estandar (.c / main.c) produciendo un arbol de sintaxis abstracta (AST) puro mediante combinadores de Gram.

---

## Modos De Operacion Y Sesion

El analizador opera de forma aislada a traves de la clase `Session` de Gram (`C_SESSION`):

- **Aislamiento lexico:** Las palabras reservadas y simbolos registrados para C no colisionan con las reglas de EasyC.
- **Comentarios:** Configurado con `//` para comentarios de linea simple (`config.LEXER_COMMENT_TOKEN = '//'`).
- **Simbolos desactivados:** Se deshabilita `**` en el mapa de simbolos mediante `tokens.disabled_symbol('**')` para permitir punteros dobles y desreferenciacion consecutiva sin interpretar potencia aritmetica.
- **Migracion de sesion:** Al importar el modulo se ejecuta `C_SESSION.migrate()` para almacenar el estado lexico y permitir alternar entre lenguajes mediante `C_SESSION.load()`.

---

## Catalogo De Reglas Sintacticas (syntax/items/)

### value.py (Tipos, Punteros Y Parametros)
- **Tipos intrinsecos:** void, char, short, int, long, float, double, bool, _Bool, _Complex.
- **Tipos compuestos:** long long, signed, unsigned.
- **Calificadores:** const, volatile, restrict, _Atomic.
- **Punteros:** Secuencia de uno o mas asteriscos (`*`).
- **Parametros (`PAIR_PARAM`):** Soporta parametros con nombre (`int x`), anonimos para prototipos (`int`, `char*`) y elipsis variadica (`...`).
- **Parametros agrupados (`PARAMETERS`):** Enclosure de parentesis con separador por comas o palabra clave `void`.
- **Argumentos (`ARGUMENTS`):** Lista de expresiones separadas por comas entre parentesis para llamadas a funcion.
- **Retorno (`RETURN`):** `return [expresion];` con punto y coma obligatorio.

### call.py (Llamadas A Funcion)
- **Llamada como expresion (`CALL`):** Identificador seguido de argumentos entre parentesis: `ident(args)`.
- **Llamada como sentencia (`CALL_STMT`):** Llamada terminada en punto y coma: `ident(args);`.

### var_decl.py (Variables Y Asignaciones)
- **Declaracion con valor (`VAR_DECLARATION`):** `[storage] [qualifier] tipo [*] ident = valor;`.
- **Declaracion simple (`VAR_INITIALIZATION`):** `[storage] [qualifier] tipo [*] ident;`.
- **Especificadores de almacenamiento:** static, extern, auto, register.
- **Asignacion (`VAR_ASSIGNATION`):** `ident op valor;` con operadores `=`, `+=`, `-=`, `*=`, `/=`, `%=`, `&=`, `|=`, `^=`, `<<=`, `>>=`.
- **Declaracion en linea (`VAR_INLINE`):** Variante sin punto y coma para clausulas iniciales de bucles for: `int i = 0`.

### func_decl.py (Funciones Y Prototipos)
- **Especificadores:** static, inline, extern.
- **Firma (`FUNCTION_SIGNATURE`):** `[especificadores] tipo [*] ident(parametros)`.
- **Prototipo (`FUNCTION_PROTOTYPE`):** Firma terminada en punto y coma (`firma;`).
- **Definicion (`FUNCTION`):** Firma seguida de bloque de sentencias delimitado por llaves `{ ... }`.

### struct_decl.py (Estructuras Y Uniones)
- **Campos (`STRUCT_FIELD`):** `tipo [*] ident;`.
- **Cuerpo (`STRUCT_BODY`):** Bloque de campos encerrado en llaves `{ ... }`.
- **Declaracion struct (`STRUCT`):** `struct ident [{ ... }];`.
- **Declaracion union (`UNION`):** `union ident [{ ... }];`.

### enum_decl.py (Enumeraciones)
- **Item enum (`ENUM_ITEM`):** Identificador con asignacion opcional: `IDENT` o `IDENT = numero`.
- **Cuerpo enum (`ENUM_BODY`):** Lista de items separados por coma entre llaves `{ ... }`.
- **Declaracion enum (`ENUM`):** `enum ident [{ ... }];`.

### typealias_decl.py (Typedef)
- **Declaracion typedef (`TYPEDEF`):** `typedef [struct|union|enum] tipo [*] ident;`. Permite definir alias de tipos directos y alias de estructuras u opacos.

### statements.py (Sentencias Y Control De Flujo)
- **Bloque de sentencias (`STATEMENT_BLOCK`):** Conjunto de instrucciones delimitado por llaves `{ ... }`.
- **Condicional (`IF`):** `if (condicion) bloque [else if (condicion) bloque] [else bloque]`.
- **Bucle while (`WHILE`):** `while (condicion) bloque_o_sentencia`.
- **Bucle do-while (`DO_WHILE`):** `do bloque_o_sentencia while (condicion);`.
- **Bucle for (`FOR`):** `for (inicio; condicion; incremento) bloque_o_sentencia`.
- **Control de saltos:** `break;`, `continue;`.

### imports.py (Preprocesador E Inclusiones)
- **Inclusion de cabecera (`INCLUDE`):** Soporta `#include <header.h>` e `#include "header.h"`.
- **Directiva pragma (`PRAGMA`):** `#pragma identificador [parametros]`.

---

## Composicion Del AST (core/frontend/C/__init__.py)

El frontend unifica las expresiones y reglas maestras en el punto de entrada:

- **Expresiones duales (`DUEXPR`):** Regla `DualExpr` que procesa precedencia y operadores de Gram entre llamadas, identificadores, numeros, cadenas, caracteres y literales.
- **Resolucion tardia de `VALUE`:** `VALUE.entrypoint = Alt(DUEXPR, CALL, BOOL, NULL, IDENT, STRING, CHAR, NUMBER)`.
- **Regla de entrada (`ENTRYPOINT`):** Alternativa global que acepta directivas de inclusion, pragma, typedef, struct, union, enum, funciones, variables, asignaciones y sentencias de control. Se asigna a `C_SESSION.entrypoint`.

---

## Flujo En El Compilador

1. El compilador recibe un archivo `.c` en `core/compiler/control.py`.
2. Se activa la sesion con `C.C_SESSION.load()`.
3. Se ejecuta el tokenizador: `TKNS = C.C_SESSION.tokenize(content, path.name)`.
4. Se ejecuta el parser generando el AST: `C.C_SESSION.parse(TKNS, path.name)`. Retorna codigo de lenguaje `0`.
5. En `core/compiler/__init__.py`, al recibir `LANG == 0`, se despacha el AST al procesador semantico de C: `core.frontend.C.processor.process(self, AST)`.
6. El procesador recorre los nodos raiz y deriva a los modulos correspondientes en `core/frontend/C/tools/` (variable, function, structure, enumeration, typedef, includes).
