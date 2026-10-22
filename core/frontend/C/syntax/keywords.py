from gram import lexer

GROUPS = {
    'types': '#3B82F6',
    'signed_': '#60A5FA',
}

# Tipos fundamentales puros de C
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

# Modificadores de signo
SIGNED_TYPES = {
    'signed': '#60A5FA',
    'unsigned': '#60A5FA',
}

TYPES = list(INTRINSIC_TYPES.keys())


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