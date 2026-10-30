from gram import lexer
from gram.core.lexer import tokens

from core.globvars import CLAUSES

# `**` se tokeniza como dos `*` para permitir niveles de puntero (`**: tipo`)
# en lugar de exponenciacion, que no forma parte de la sintaxis Bagron actual.
tokens.disabled_symbol('**')

GROUPS = {
    'imports': '#E5C07B',
    'types': '#004177',
    'privacy': '#2874A6',
    'clauses': '#33FF00',
    'keywords': '#FFFFFF',
    'conditional_statement': '#7D5DF0',
    'loops': '#D16969',
    'skipers': '#F50000',
}

KEYWORDS = {
    # Control de flujo y sentencias
    'func': '#D16969',
    'return': '#FD2008',
    'pass': '#220502',
    'global': '#FFFFFF',
    'break': '#F50000',
    'continue': '#F50000',
    'Del': '#F50000',

    # Condicionales
    'if': '#7D5DF0',
    'elif': '#7D5DF0',
    'else': '#7D5DF0',
    'not': '#C0392B',

    # Bucles e iteradores
    'for': '#D16969',
    'while': '#D16969',
    'ran': '#D16969',
    'in': '#D16969',

    # Módulos, imports y cláusulas
    'import': '#E5C07B',
    'extern': '#E5C07B',
    'from': '#E5C07B',
    'clause': '#F5D15D',

    # Visibilidad
    'public': '#2874A6',
    'private': '#2874A6',

    # Declaraciones de tipos y estructuras
    'class': '#6630E4',
    'struct': '#17A2B8',
    'enum': '#17A2B8',
    'mold': '#17A2B8',
    'flags': '#17A2B8',

    # Modificadores de bajo nivel
    'inline': '#E2B93D',
    'packed': '#E2B93D',
    'align': '#E2B93D',
    'volatile': '#E2B93D',

    # Literales y utilidades del sistema
    'Null': '#F50000',
    'true': '#4E0097',
    'false': '#4E0097',
    'as': '#FFFFFF',
    'const': '#FFFFFF',
    'unique': '#FFFFFF',
    'asm': '#AD0997',

    # preprocesadores
    "prep": "#AD0997"
}

INTRINSIC_TYPES = {
    # Enteros con y sin signo
    'int8': '#3B82F6',
    'int16': '#3B82F6',
    'int32': '#3B82F6',
    'int64': '#3B82F6',
    'uint8': '#3B82F6',
    'byte': '#3B82F6',
    'uint16': '#3B82F6',
    'uint32': '#3B82F6',
    'uint64': '#3B82F6',
    'usize': '#3B82F6',
    'isize': '#3B82F6',

    # Punto flotante (16, 32, 64 bits)
    'middle': '#3B82F6',
    'float': '#3B82F6',
    'double': '#3B82F6',

    # Caracteres, cadenas, booleanos y tipos especiales
    'char': '#3B82F6',
    'chain': '#3B82F6', # array de carácteres
    'bool': '#3B82F6',
    'void': '#3B82F6',
    'Never': '#3B82F6',
    'Len_t': '#3B82F6', # hidden compile-time array length parameter
    'Size_t': '#3B82F6', # hidden compile-time byte-size parameter
    'Region_t': '#3B82F6', # hidden immutable provenance parameter
    'callptr': '#3B82F6',
    'Bint': '#3B82F6',
    'uBint': '#3B82F6',

}

TYPES = list(INTRINSIC_TYPES.keys())


KEYWORDS_BY_GROUP = {
    'imports': [
        'import',
        'extern',
        'from',
    ],
    'clauses': CLAUSES,
    'privacy': [
        'public',
        'private',
    ],
    'conditional_statement': [
        'if',
        'elif',
        'else',
        'not',
    ],
    'loops': [
        'for',
        'while',
        'ran',
        'in',
    ],
    'skipers': [
        'continue',
        'break',
    ],
    'keywords': [
        'func',
        'Del',
        'as',
        'clause',
        'return',
        'global',
        'pass',
        'inline',
        'packed',
        'align',
        'volatile',
        'struct',
        'enum',
        'mold',
        'flags',
        'class',
        'const',
        'Null',
        'true',
        'false',
        'asm',
    ],
    'preprocessors': [
        'prep'
    ]
}


# 1. Registrar grupos
for group, color in GROUPS.items():
    if not color:
        lexer.words.add_group(group)
    else:
        lexer.words.add_group(group, color_group=color)
   
# 2. Registrar tipos intrínsecos en el grupo 'types'     
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

# 3. Registrar palabras clave por grupo
for group, words in KEYWORDS_BY_GROUP.items():
    for word in words:
        color = KEYWORDS.get(word, GROUPS.get(group, '#FFFFFF'))
        lexer.words.add_keyword(
            word,
            hex_color=color,
            group=group,
            allow_override=True,
        )

# 4. Registrar palabras clave individuales restantes
for kw, color in KEYWORDS.items():
    if not lexer.words.keyword_exists(kw):
        lexer.words.add_keyword(
            kw,
            hex_color=color or '#FFFFFF',
            group='keywords',
            allow_override=True,
        )
    else:
        k_obj = lexer.words.get_keyword(kw)
        if k_obj and color:
            k_obj.hex_color = color
