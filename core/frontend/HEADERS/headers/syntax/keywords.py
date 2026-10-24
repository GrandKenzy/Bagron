from gram import lexer
from gram.core.lexer import tokens

tokens.disabled_symbol('**')

GROUPS = {
    'types': '#3B82F6',
    'signed_': '#60A5FA',
    'qualifiers': '#FFFFFF',
    'function_specifiers': '#E2B93D',
    'storage_specifiers': '#2874A6',
    'alignment_specifiers': '#C586C0',
    'typeof_specifiers': '#C586C0',
    'tag_specifiers': '#17A2B8',
    'attribute_specifiers': '#E5C07B',
    'keywords': '#89B1E2',
}

INTRINSIC_TYPES = {
    'void': '#3B82F6',
    'char': '#3B82F6',
    'short': '#3B82F6',
    'int': '#3B82F6',
    'long': '#3B82F6',
    'float': '#3B82F6',
    'double': '#3B82F6',
    'bool': '#3B82F6',
    '_Bool': '#3B82F6',
    '_Complex': '#3B82F6',
    '_Imaginary': '#3B82F6',
    '_BitInt': '#3B82F6',
    '_Decimal32': '#3B82F6',
    '_Decimal64': '#3B82F6',
    '_Decimal128': '#3B82F6',
}

SIGNED_TYPES = {
    'signed': '#60A5FA',
    'unsigned': '#60A5FA',
    '__signed': '#60A5FA',
    '__signed__': '#60A5FA',
}

QUALIFIERS = {
    'const': '#FFFFFF',
    'volatile': '#E2B93D',
    'restrict': '#E2B93D',
    '_Atomic': '#E2B93D',
    '__restrict': '#E2B93D',
    '__restrict__': '#E2B93D',
    '__const': '#FFFFFF',
    '__const__': '#FFFFFF',
    '__volatile': '#E2B93D',
    '__volatile__': '#E2B93D',
}

FUNCTION_SPECIFIERS = {
    'inline': '#E2B93D',
    '_Noreturn': '#E2B93D',
    '__inline': '#E2B93D',
    '__inline__': '#E2B93D',
    '__forceinline': '#E2B93D',
    '__stdcall': '#E2B93D',
    '__cdecl': '#E2B93D',
    '__fastcall': '#E2B93D',
    '__thiscall': '#E2B93D',
}

STORAGE_SPECIFIERS = {
    'extern': '#2874A6',
    'static': '#2874A6',
    'auto': '#2874A6',
    'register': '#2874A6',
    '_Thread_local': '#2874A6',
    'thread_local': '#2874A6',
    'constexpr': '#2874A6',
    'typedef': '#007535',
}

ALIGNMENT_SPECIFIERS = {
    '_Alignas': '#C586C0',
    'alignas': '#C586C0',
}

TYPEOF_SPECIFIERS = {
    'typeof': '#C586C0',
    'typeof_unqual': '#C586C0',
    '__typeof__': '#C586C0',
    '__typeof': '#C586C0',
}

TAG_SPECIFIERS = {
    'struct': '#17A2B8',
    'union': '#17A2B8',
    'enum': '#17A2B8',
}

ATTRIBUTE_SPECIFIERS = {
    '__attribute__': '#E5C07B',
    '__attribute': '#E5C07B',
    '__declspec': '#E5C07B',
    '__extension__': '#E5C07B',
    '__asm__': '#E5C07B',
    '__asm': '#E5C07B',
    'asm': '#E5C07B',
}

KEYWORDS = {
    'return': '#FD2008',
    'break': '#F50000',
    'continue': '#F50000',
    'goto': '#FD2008',
    'if': '#7D5DF0',
    'else': '#7D5DF0',
    'switch': '#7D5DF0',
    'case': '#7D5DF0',
    'default': '#7D5DF0',
    'for': '#D16969',
    'while': '#D16969',
    'do': '#D16969',
    'sizeof': '#C586C0',
    'alignof': '#C586C0',
    '_Alignof': '#C586C0',
    '_Generic': '#C586C0',
    'static_assert': '#C586C0',
    '_Static_assert': '#C586C0',
    'NULL': '#F50000',
    'nullptr': '#F50000',
    'true': '#4E0097',
    'false': '#4E0097',
    '_Pragma': '#E5C07B',
    '__FILE__': '#E5C07B',
    '__LINE__': '#E5C07B',
    '__DATE__': '#E5C07B',
    '__TIME__': '#E5C07B',
    '__STDC__': '#E5C07B',
    '__STDC_VERSION__': '#E5C07B',
    '__func__': '#E5C07B',
}

TYPES = list(INTRINSIC_TYPES.keys())

for group, color in GROUPS.items():
    if not color:
        lexer.words.add_group(group)
    else:
        lexer.words.add_group(group, color_group=color)

CATEGORIES = [
    (INTRINSIC_TYPES, 'types'),
    (SIGNED_TYPES, 'signed_'),
    (QUALIFIERS, 'qualifiers'),
    (FUNCTION_SPECIFIERS, 'function_specifiers'),
    (STORAGE_SPECIFIERS, 'storage_specifiers'),
    (ALIGNMENT_SPECIFIERS, 'alignment_specifiers'),
    (TYPEOF_SPECIFIERS, 'typeof_specifiers'),
    (TAG_SPECIFIERS, 'tag_specifiers'),
    (ATTRIBUTE_SPECIFIERS, 'attribute_specifiers'),
    (KEYWORDS, 'keywords'),
]

for group_dict, group_name in CATEGORIES:
    for keyword, color in group_dict.items():
        kw_obj = lexer.words.add_keyword(
            keyword,
            hex_color=color,
            group=group_name,
            allow_override=True
        )
        grp = lexer.words.get_group(group_name)
        if grp and keyword not in grp.values:
            grp.add_keyword(kw_obj)