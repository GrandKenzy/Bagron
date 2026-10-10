import gram

gram.config.LEXER_COMMENT_TOKEN = ';'
gram.config.LEXER_SAVE_COMMENTS = False

GROUPS = [
    'imports',
    'types',
    'privacity',
    'clauses',
    'properties',
    'keywords',
    'conditional_statement',
    'loops',
]

GROUP_COLORS = {
    'types': '#4FA6ED',
    'privacity': '#2874A6',
    'conditional_statement': '#C0392B',
    'loops': '#D16969',
    'imports': '#E5C07B',
    'clauses': '#D4AF37',
    'properties': '#E5C07B',
    'keywords': '#E5C07B',
}

KEYWORD_SPECIFIC_COLORS = {
    '__int_t__': '#3B82F6',
    '__int8_t__': '#3B82F6',
    '__int16_t__': '#3B82F6',
    '__int32_t__': '#3B82F6',
    '__int64_t__': '#3B82F6',
    '__uint_t__': '#3B82F6',
    '__uint8_t__': '#3B82F6',
    '__uint16_t__': '#3B82F6',
    '__uint32_t__': '#3B82F6',
    '__uint64_t__': '#3B82F6',
    '__float_t__': '#3B82F6',
    '__middle_t__': '#3B82F6',
    '__double_t__': '#3B82F6',
    '__char_t__': '#3B82F6',
    '__str_t__': '#3B82F6',
    '__bool_t__': '#3B82F6',
    '__ptr_t__': '#3B82F6',
    '__void_t__': '#3B82F6',
    '__type_t__': '#3B82F6',
    '__arrof__': '#3B82F6',
    '__void_p_t__': '#3B82F6',
    '__size_t__': '#3B82F6',
    'return': '#C0392B',
    'pass': '#C0392B',
    'if': '#C0392B',
    'elif': '#C0392B',
    'else': '#C0392B',
    'not': '#C0392B',
    'for': '#D16969',
    'in': '#D16969',
    'ran': '#D16969',
    'rand': '#D16969',
    'unsafe': '#B03A2E',
    'try': '#B03A2E',
    'catch': '#B03A2E',
    'lambda': '#B03A2E',
    '__init__': '#E2B93D',
    '__new__': '#E2B93D',
    '__fronted__': '#E2B93D',
    '__setv__': '#E2B93D',
    '__member__': '#E2B93D',
    '__method__': '#E2B93D',
    '__size__': '#E2B93D',
    '__inline__': '#E2B93D',
    '__slot__': '#E2B93D',
    '__type__': '#E2B93D',
    '__items__': '#E2B93D',
    '__dtype__': '#E2B93D',
    '__getter__': '#E2B93D',
    '__setter__': '#E2B93D',
    '__getitem__': '#E2B93D',
    '__setitem__': '#E2B93D',
    '__const__': '#E2B93D',
    '__visibility__': '#E2B93D',
    'class': '#17A2B8',
    'struct': '#17A2B8',
    'enum': '#17A2B8',
    'Type': '#17A2B8',
    'type': '#17A2B8',
    'Null': '#48C78E',
    'true': '#48C78E',
    'false': '#48C78E',
    'this': '#5DADE2',
    'self': '#5DADE2',
}

INTRINSIC_TYPES = [
    '__int_t__',
    '__int8_t__',
    '__int16_t__',
    '__int32_t__',
    '__int64_t__',
    '__uint_t__',
    '__uint8_t__',
    '__uint16_t__',
    '__uint32_t__',
    '__uint64_t__',
    '__float_t__',
    '__middle_t__',
    '__double_t__',
    '__char_t__',
    '__str_t__',
    '__bool_t__',
    '__ptr_t__',
    '__void_t__',
    '__type_t__',
    '__arrof__',
    '__void_p_t__',
    '__size_t__',
]

TYPES = list(INTRINSIC_TYPES) + [
    'pointer',
    'void',
    'char',
    'double',
    'float',
    'middle',
    'int',
    'int8',
    'int16',
    'int32',
    'int64',
    'uint',
    'uint8',
    'uint16',
    'uint32',
    'uint64',
    'str',
    'ptr',
    'bool',
    'type',
    '__dtype__',
    'any',
]

ADVANCE_TYPES = [
    'struct',
    'enum'
]

SPECIAL_KEYWORDS = [
    'lambda',
    'unsafe',
    'try',
    'catch',
]

KEYWORDS_BY_GROUP = {
    'imports': ['include', 'import', 'object'],
    'clauses': ['Visibility', 'Arch', 'Target', 'System', 'StackLImit', 'StackLimit'],
    'properties': ['mode'],
    'privacity': ['public', 'private'],
    'conditional_statement': ['if', 'elif', 'else', 'not'],
    'loops': ['for', 'ran', 'rand', 'in'],
    'keywords': ['as', 'clause', 'property', 'return', '__init__', '__new__', '__fronted__', '__setv__', '__member__', '__method__', 'pass', 'this', 'self', '__size__', '__inline__', '__slot__', '__type__', '__items__', '__dtype__', '__getter__', '__setter__', '__getitem__', '__setitem__', '__const__', '__visibility__', 'Type', 'type', 'struct', 'enum', 'method', 'class'],
}

for group in GROUPS:
    g_color = GROUP_COLORS.get(group, '#E5C07B')
    gram.words.add_group(group, color_group=g_color)

for kw in TYPES:
    color = KEYWORD_SPECIFIC_COLORS.get(kw, GROUP_COLORS.get('types', '#4FA6ED'))
    gram.words.add_keyword(kw, hex_color=color, group='types', allow_override=True)

for group, words in KEYWORDS_BY_GROUP.items():
    for word in words:
        color = KEYWORD_SPECIFIC_COLORS.get(word, GROUP_COLORS.get(group, '#E5C07B'))
        gram.words.add_keyword(word, hex_color=color, group=group, allow_override=True)

for kw, color in KEYWORD_SPECIFIC_COLORS.items():
    if not gram.words.keyword_exists(kw):
        gram.words.add_keyword(kw, hex_color=color, group='keywords', allow_override=True)
    else:
        k_obj = gram.words.get_keyword(kw)
        if k_obj:
            k_obj.hex_color = color

for kw in ['name', 'sep', 'only', 'exclude', 'symbols', 'values', 'mode']:
    if gram.words.keyword_exists(kw):
        gram.words.remove_keyword(kw)
