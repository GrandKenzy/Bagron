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

for group in GROUPS:
    gram.words.add_group(group)

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

for kw in TYPES:
    gram.words.add_keyword(kw, group='types', allow_override=True)

for group, words in KEYWORDS_BY_GROUP.items():
    for word in words:
        gram.words.add_keyword(word, group=group, allow_override=True)

for kw in ['name', 'sep', 'only', 'exclude', 'symbols', 'values', 'mode']:
    if gram.words.keyword_exists(kw):
        gram.words.remove_keyword(kw)
