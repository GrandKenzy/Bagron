from gram import lexer
from gram.core.lexer import tokens

tokens.disabled_symbol('**')

# Convención de comentarios:
#   # C23      -> estándar en el que apareció (sigue soportado)
#   # C89-C17  -> apareció en C89 y dejó de soportarse después de C17
#   # Nota:    -> caso especial de uso o de sintaxis

GROUPS = {
    'types': '#3B82F6',
    'signed_': "#89B1E2",
    'qualifiers': "#E2B93D",
    'function_specifiers': "#E2B93D",
    'keywords': "#89B1E2",
}

# Tipos fundamentales puros de C
INTRINSIC_TYPES = {
    'void': '#3B82F6',                  # C89
    'char': '#3B82F6',                  # C89
    'short': '#3B82F6',                 # C89
    'int': '#3B82F6',                   # C89
    # Nota: 'long long' existe desde C99; 'long double' desde C89
    'long': '#3B82F6',                  # C89
    'float': '#3B82F6',                 # C89
    'double': '#3B82F6',                # C89
    # Nota: en C99-C17 'bool' es solo un macro de <stdbool.h>; en C23 es keyword
    'bool': '#3B82F6',                  # C23
    '_Bool': '#3B82F6',                 # C99
    # Nota: nunca va sola; se combina con float, double o long double (float _Complex)
    '_Complex': '#3B82F6',              # C99
    # Nota: opcional (Anexo G); casi ningún compilador la implementa
    '_Imaginary': '#3B82F6',            # C99
    # Nota: se usa siempre como _BitInt(N), con N constante >= 1; admite signed/unsigned
    '_BitInt': '#3B82F6',               # C23
    # Nota: los _Decimal* son opcionales; dependen de que la implementación los soporte
    '_Decimal32': '#3B82F6',            # C23
    '_Decimal64': '#3B82F6',            # C23
    '_Decimal128': '#3B82F6',           # C23
}

# Modificadores de signo
SIGNED_TYPES = {
    'signed': '#60A5FA',                # C89
    'unsigned': '#60A5FA',              # C89
}

# Calificadores de tipo
QUALIFIERS = {
    'const': '#FFFFFF',                 # C89
    'volatile': '#E2B93D',              # C89
    # Nota: solo se aplica a punteros (int *restrict p)
    'restrict': '#E2B93D',              # C99
    # Nota: doble uso; calificador (_Atomic int) y especificador (_Atomic(int))
    '_Atomic': '#E2B93D',               # C11
}

# Especificadores de función
FUNCTION_SPECIFIERS = {
    'inline': '#E2B93D',                # C99
    # Nota: obsoleta desde C23, se prefiere el atributo [[noreturn]]; sigue soportada
    '_Noreturn': '#E2B93D',             # C11
}

TYPES = list(INTRINSIC_TYPES.keys())


KEYWORDS = {
    # Control de flujo y sentencias
    'return': '#FD2008',                # C89
    'break': '#F50000',                 # C89
    'continue': '#F50000',              # C89
    'goto': '#FD2008',                  # C89

    # Condicionales
    'if': '#7D5DF0',                    # C89
    'else': '#7D5DF0',                  # C89
    'switch': '#7D5DF0',                # C89
    'case': '#7D5DF0',                  # C89
    # Nota: también se usa dentro de _Generic(expr, tipo: valor, default: valor)
    'default': '#7D5DF0',               # C89

    # Bucles e iteradores
    'for': '#D16969',                   # C89
    'while': '#D16969',                 # C89
    'do': '#D16969',                    # C89

    # Operadores
    # Nota: se usa como sizeof expr o como sizeof(tipo)
    'sizeof': '#C586C0',                # C89

    # Módulos, imports y cláusulas
    # Nota: solo va después de '#'; el header va entre <...> o "..."
    'include': '#E5C07B',               # C89

    # Visibilidad y almacenamiento
    'extern': '#2874A6',                # C89
    'static': '#2874A6',                # C89
    # Nota: en C89-C17 es solo clase de almacenamiento; en C23 también infiere el tipo (auto x = 5;)
    'auto': '#2874A6',                  # C89
    'register': '#2874A6',              # C89
    # Nota: en C11-C17 'thread_local' es un macro de <threads.h>; en C23 es keyword
    '_Thread_local': '#2874A6',         # C11
    'thread_local': '#2874A6',          # C23
    # Nota: solo para objetos (no para funciones como en C++)
    'constexpr': '#2874A6',             # C23

    # Declaraciones de tipos y estructuras
    'struct': '#17A2B8',                # C89
    'union': '#17A2B8',                 # C89
    'enum': '#17A2B8',                  # C89
    'typedef': '#007535',               # C89

    # C11 / C23
    # Nota: en C11-C17 'alignas' y 'alignof' son macros de <stdalign.h>; en C23 son keywords
    # Nota: _Alignas se usa como _Alignas(N) o _Alignas(tipo)
    '_Alignas': '#C586C0',              # C11
    'alignas': '#C586C0',               # C23
    '_Alignof': '#C586C0',              # C11
    'alignof': '#C586C0',               # C23
    # Nota: se usa como _Generic(expr, tipo: valor, ..., default: valor)
    '_Generic': '#C586C0',              # C11
    # Nota: en C11-C17 'static_assert' es un macro de <assert.h>; en C23 es keyword
    '_Static_assert': '#C586C0',        # C11
    'static_assert': '#C586C0',         # C23
    # Nota: se usa como typeof(expr) o typeof(tipo); antes era extensión de GCC/Clang
    'typeof': '#C586C0',                # C23
    'typeof_unqual': '#C586C0',         # C23

    # Literales y utilidades del sistema
    # Nota: es un macro de <stddef.h> / <stdio.h>, no una keyword del lenguaje
    'NULL': '#F50000',                  # C89
    # Nota: de tipo nullptr_t
    'nullptr': '#F50000',               # C23
    # Nota: en C99-C17 'true' y 'false' son macros de <stdbool.h>; en C23 son keywords
    'true': '#4E0097',                  # C23
    'false': '#4E0097',                 # C23

    # Preprocesador
    # Nota: todas las directivas van después de '#'
    'pragma': '#E5C07B',                # C89
    'define': '#E5C07B',                # C89
    'undef': '#E5C07B',                 # C89
    'elif': '#E5C07B',                  # C89
    'elifdef': '#E5C07B',               # C23
    'elifndef': '#E5C07B',              # C23
    'endif': '#E5C07B',                 # C89
    'ifdef': '#E5C07B',                 # C89
    'ifndef': '#E5C07B',                # C89
    'error': '#E5C07B',                 # C89
    # Nota: era una extensión común; entró al estándar en C23
    'warning': '#E5C07B',               # C23
    'line': '#E5C07B',                  # C89
    # Nota: incrusta un archivo binario como datos (#embed "archivo")
    'embed': '#E5C07B',                 # C23
    # Nota: operador de #if / #elif; se usa como defined X o defined(X)
    'defined': '#E5C07B',               # C89
    # Nota: operadores de #if / #elif; se usan como __has_include(<h>), etc.
    '__has_include': '#E5C07B',         # C23
    '__has_embed': '#E5C07B',           # C23
    '__has_c_attribute': '#E5C07B',     # C23
    # Nota: solo dentro del cuerpo de un macro variádico
    '__VA_ARGS__': '#E5C07B',           # C99
    # Nota: solo en macros variádicos; se usa como __VA_OPT__(...)
    '__VA_OPT__': '#E5C07B',            # C23
    # Nota: operador que reemplaza a #pragma dentro de macros; se usa como _Pragma("...")
    '_Pragma': '#E5C07B',               # C99

    # Predefinidos (el preprocesador / compilador inserta algo al verlos)
    '__FILE__': '#E5C07B',              # C89
    '__LINE__': '#E5C07B',              # C89
    '__DATE__': '#E5C07B',              # C89
    '__TIME__': '#E5C07B',              # C89
    '__STDC__': '#E5C07B',              # C89
    '__STDC_VERSION__': '#E5C07B',      # C95
    # Nota: no es un macro; el compilador lo declara implícitamente dentro de cada función
    '__func__': '#E5C07B',              # C99
}

# 1. Registrar grupos
for group, color in GROUPS.items():
    if not color:
        lexer.words.add_group(group)
    else:
        lexer.words.add_group(group, color_group=color)

# 2. Registrar tipos fundamentales en el grupo 'types'
for keyword in TYPES:
    color = INTRINSIC_TYPES.get(keyword, GROUPS['types'])
    kw_obj = lexer.words.add_keyword(
        keyword,
        hex_color=color,
        group='types',
        allow_override=True
    )
    grp_t = lexer.words.get_group('types')
    if grp_t and keyword not in grp_t.values:
        grp_t.add_keyword(kw_obj)

# 3. Registrar signed / unsigned en el grupo 'signed_'
for keyword, color in SIGNED_TYPES.items():
    kw_obj = lexer.words.add_keyword(
        keyword,
        hex_color=color,
        group='signed_',
        allow_override=True
    )
    grp_s = lexer.words.get_group('signed_')
    if grp_s and keyword not in grp_s.values:
        grp_s.add_keyword(kw_obj)

# 4. Registrar calificadores en el grupo 'qualifiers'
for keyword, color in QUALIFIERS.items():
    kw_obj = lexer.words.add_keyword(
        keyword,
        hex_color=color,
        group='qualifiers',
        allow_override=True
    )
    grp_q = lexer.words.get_group('qualifiers')
    if grp_q and keyword not in grp_q.values:
        grp_q.add_keyword(kw_obj)

# 5. Registrar especificadores de función en el grupo 'function_specifiers'
for keyword, color in FUNCTION_SPECIFIERS.items():
    kw_obj = lexer.words.add_keyword(
        keyword,
        hex_color=color,
        group='function_specifiers',
        allow_override=True
    )
    grp_f = lexer.words.get_group('function_specifiers')
    if grp_f and keyword not in grp_f.values:
        grp_f.add_keyword(kw_obj)

# 6. Registrar keywords en el grupo 'keywords'
for keyword, color in KEYWORDS.items():
    kw_obj = lexer.words.add_keyword(
        keyword,
        hex_color=color,
        group='keywords',
        allow_override=True
    )
    grp_k = lexer.words.get_group('keywords')
    if grp_k and keyword not in grp_k.values:
        grp_k.add_keyword(kw_obj)