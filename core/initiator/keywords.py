import gram

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

TYPES = [
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
    'imports': ['include', 'import', 'class'],
    'clauses': ['Visibility', 'Arch', 'Target', 'System', 'StackLImit', 'StackLimit'],
    'properties': ['mode'],
    'privacity': ['public', 'private'],
    'conditional_statement': ['if', 'elif', 'else', 'not'],
    'loops': ['for', 'ran', 'rand', 'in'],
    'keywords': ['as', 'clause', 'property', 'return', '__init__', '__setv__', '__member__', '__method__', 'pass', 'this', '__size__'],
}

for kw in TYPES:
    gram.words.add_keyword(kw, group='types')

for group, words in KEYWORDS_BY_GROUP.items():
    for word in words:
        gram.words.add_keyword(word, group=group, allow_override=True)

for kw in ['name', 'sep', 'only', 'exclude', 'symbols', 'values', 'mode']:
    if gram.words.keyword_exists(kw):
        gram.words.remove_keyword(kw)
