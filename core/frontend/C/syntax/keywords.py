from gram import lexer
from gram.core.lexer import tokens

tokens.disabled_symbol('**')

GROUPS = {
    'types': '#3B82F6',
    'signed_': '#60A5FA',
    'qualifiers': '#E2B93D',
    'storage': '#E2B93D',
    'control_flow': '#FD2008',
    'conditionals': '#7D5DF0',
    'loops': '#D16969',
    'skipers': '#F50000',
    'structures': '#17A2B8',
    'keywords': '#FFFFFF',
    'preprocessors': '#AD0997',
}

# Tipos fundamentales de C
INTRINSIC_TYPES = {
    'void': '#3B82F6',
    'char': '#3B82F6',
    'short': '#3B82F6',
    'int': '#3B82F6',
    'long': '#3B82F6',
    'float': '#3B82F6',
    'double': '#3B82F6',
    'bool': '#3B82F6',      # C23
    '_Bool': '#3B82F6',     # C99 - C17
    '_Complex': '#3B82F6',
}

SIGNED_TYPES = {
    'signed': '#60A5FA',
    'unsigned': '#60A5FA',
}

QUALIFIERS = {
    'const': '#E2B93D',
    'volatile': '#E2B93D',
    'restrict': '#E2B93D',
    '_Atomic': '#E2B93D',
}

STORAGE_CLASSES = {
    'static': '#E2B93D',
    'extern': '#E2B93D',
    'inline': '#E2B93D',
    'register': '#E2B93D',
    'auto': '#E2B93D',
}

KEYWORDS = {
    # control de flujos y saltos
    'return': '#FD2008',
    'break': '#F50000',
    'continue': '#F50000',
    'goto': '#F50000',

    # condicionales
    'if': '#7D5DF0',
    'else': '#7D5DF0',
    'switch': '#7D5DF0',
    'case': '#7D5DF0',
    'default': '#7D5DF0',

    # bucles
    'for': '#D16969',
    'while': '#D16969',
    'do': '#D16969',

    # Declaraciones y agregados
    'struct': '#17A2B8',
    'union': '#17A2B8',
    'enum': '#17A2B8',
    'typedef': '#17A2B8',

    # Operadores y utilidades de lenguaje.
    'sizeof': '#FFFFFF',
    'NULL': '#F50000',
    'Null': '#F50000',
    'true': '#4E0097',
    'false': '#4E0097',

    # directives y preprocesador
    'include': '#AD0997',
    'define': '#AD0997',
    'undef': '#AD0997',
    'ifdef': '#AD0997',
    'ifndef': '#AD0997',
    'endif': '#AD0997',
    'pragma': '#AD0997',
}

TYPES = list(INTRINSIC_TYPES.keys())

KEYWORDS_BY_GROUP = {
    'qualifiers': list(QUALIFIERS.keys()),
    'storage': list(STORAGE_CLASSES.keys()),
    'conditionals': ['if', 'else', 'switch', 'case', 'default'],
    'loops': ['for', 'while', 'do'],
    'skipers': ['return', 'break', 'continue', 'goto'],
    'structures': ['struct', 'union', 'enum', 'typedef'],
    'preprocessors': ['include', 'define', 'undef', 'ifdef', 'ifndef', 'endif', 'pragma'],
    'keywords': ['sizeof', 'NULL', 'Null', 'true', 'false'],
}

# 1. Registrar grupos
for group, color in GROUPS.items():
    if not color:
        lexer.words.add_group(group)
    else:
        lexer.words.add_group(group, color_group=color)

# 2. Registrar tipos fundamentales en 'types'
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

# 3. Registrar signed / unsigned en 'signed_'
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

# r eegistrar palabras clave por grupo
for group, words_list in KEYWORDS_BY_GROUP.items():
    for word in words_list:
        color = KEYWORDS.get(word, QUALIFIERS.get(word, STORAGE_CLASSES.get(word, GROUPS.get(group, '#FFFFFF'))))
        kw_obj = lexer.words.add_keyword(
            word,
            hex_color=color,
            group=group,
            allow_override=True,
        )
        grp = lexer.words.get_group(group)
        if grp and word not in grp.values:
            grp.add_keyword(kw_obj)

# restantes
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