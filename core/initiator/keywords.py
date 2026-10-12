import gram

gram.config.LEXER_COMMENT_TOKEN = ';'
gram.config.LEXER_SAVE_COMMENTS = False
gram.words.clear_all()


GROUPS = {
    'imports': '#E5C07B',
    'types': "#004177",
    'privacity': '#2874A6',
    'clauses': "#33FF00",
    'keywords': "#FFFFFF",
    'conditional_statement': "#7D5DF0",
    'loops': '#D16969',
}

KEYWORDS = {
    'return': "#FD2008",
    'pass': "#220502",
    'if': None,
    'elif': None,
    'else': None,
    'not': '#C0392B',
    'for': None,
    'while': None,
    'in': '#C0392B',
    'ran': '#D16969',
    'clause': "#F5D15D",
    '__fronted__': '#E2B93D',
    '__inline__': '#E2B93D',
    '__packed__': '#E2B93D',
    '__slot__': '#E2B93D',
    'sizeof': '#E2B93D',
    'class': "#6630E4",
    'struct': '#17A2B8',
    'enum': '#17A2B8',
    'Type': "#007535",
    'Null': "#F50000",
    'true': "#4E0097",
    'false': "#4E0097",
}

INTRINSIC_TYPES = {
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
    '__bool_t__': '#3B82F6',
    '__type_t__': '#3B82F6',
    '__arrof__': '#3B82F6',
    '__void_p_t__': '#3B82F6',
    '__void_t__': '#3B82F6',
    '__size_t__': '#3B82F6',
}

TYPES = list(INTRINSIC_TYPES.keys())

ADVANCE_TYPES = [
    'struct',
    'enum',
]

KEYWORDS_BY_GROUP = {
    'imports': ['include', 'import', 'load', 'declare'],
    'clauses': ['Visibility', 'Arch', 'Target', 'System', 'StackLimit'],
    'privacity': ['public', 'private'],
    'conditional_statement': ['if', 'elif', 'else', 'not', 'and', 'or'],
    'loops': ['for', 'while', 'ran', 'in'],
    'keywords': ['as', 'clause', 'return', 'pass', '__fronted__', '__inline__', '__packed__', '__slot__', 'Type', 'type', 'struct', 'enum', 'method', 'class', 'sizeof', 'self', 'const', 'visibility'],
}

for group, color in GROUPS.items():
    if not color:
        gram.words.add_group(group)
    else:
        gram.words.add_group(group, color_group=color)

for keyword in TYPES:
    if keyword.startswith("__"):
        color = INTRINSIC_TYPES[keyword]
    else:
        color = GROUPS['types']
    gram.words.add_keyword(keyword, hex_color=color, group='types', allow_override=True)

for group, words in KEYWORDS_BY_GROUP.items():
    for word in words:
        color = KEYWORDS.get(word, GROUPS.get(group, "#FFFFFF"))
        gram.words.add_keyword(word, hex_color=color, group=group, allow_override=True)

for kw, color in KEYWORDS.items():
    if not gram.words.keyword_exists(kw):
        gram.words.add_keyword(kw, hex_color=color, group='keywords', allow_override=True)
    else:
        k_obj = gram.words.get_keyword(kw)
        if k_obj:
            k_obj.hex_color = color
