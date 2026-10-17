from pathlib import Path
import re
from typing import Any

from gram import ast
from gram.core.lexer import Lexer
from gram.core.parser import Parser

from core.externs.grammar import extern_grammar


def extract_directives(code: str) -> tuple[str, dict[str, Any]]:
    metadata: dict[str, Any] = {
        'header': None,
        'headers': [],
        'links': [],
        'bins': [],
        'lib_dirs': [],
        'include_dirs': [],
    }
    clean_lines = []
    for line in code.splitlines():
        trimmed = line.strip()
        code_part = trimmed.split(';')[0].strip()
        if code_part.startswith('@'):
            match = re.match(r'^@([A-Za-z0-9_]+)\s+(.+)$', code_part)
            if match:
                directive = match.group(1).lower()
                val = match.group(2).strip().strip('"\'')
                if directive in ('header', 'c_header'):
                    metadata['header'] = val
                    if val not in metadata['headers']:
                        metadata['headers'].append(val)
                elif directive in ('link', 'lib', 'l'):
                    if val not in metadata['links']:
                        metadata['links'].append(val)
                elif directive in ('bin', 'dll', 'so', 'dylib'):
                    if val not in metadata['bins']:
                        metadata['bins'].append(val)
                elif directive in ('lib_dir', 'libdir', 'l_dir'):
                    if val not in metadata['lib_dirs']:
                        metadata['lib_dirs'].append(val)
                elif directive in ('include_dir', 'includedir', 'i_dir'):
                    if val not in metadata['include_dirs']:
                        metadata['include_dirs'].append(val)
            continue
        clean_lines.append(line)
    return '\n'.join(clean_lines), metadata



def _flatten_values(node: Any) -> list[str]:
    res: list[str] = []
    if isinstance(node, ast.ASTRef):
        for child in node.nodes:
            res.extend(_flatten_values(child))
    elif isinstance(node, (list, tuple)):
        for item in node:
            res.extend(_flatten_values(item))
    elif isinstance(node, ast.ASTTokenNode):
        val = node.token.value
        if val is not None:
            res.append(str(val))
    elif isinstance(node, ast.ASTKeyword):
        val = node.token.value
        if val is not None:
            res.append(str(val))
    elif isinstance(node, str):
        res.append(node)
    return res


def _extract_type_info(type_node: Any, extra_star: bool = False) -> tuple[str, bool]:
    tokens = _flatten_values(type_node)
    is_ptr = extra_star or '*' in tokens or 'ptr' in tokens
    clean = [t for t in tokens if t not in ('*', 'ptr')]
    t_name = clean[0] if clean else 'void'
    return t_name, is_ptr



def extract_func(node: Any) -> dict[str, Any]:
    children = node.nodes if isinstance(node, ast.ASTRef) else []
    type_node = None
    has_ret_star = False
    c_name = ''
    params_node = None
    alias_name = ''

    idx = 0
    if idx < len(children) and isinstance(children[idx], ast.ASTRef) and children[idx].name == 'EXTERN_TYPE':
        type_node = children[idx]
        idx += 1

    if idx < len(children) and isinstance(children[idx], ast.ASTTokenNode) and children[idx].token.value == '*':
        has_ret_star = True
        idx += 1

    if idx < len(children) and isinstance(children[idx], ast.ASTTokenNode):
        c_name = str(children[idx].token.value)
        idx += 1

    if idx < len(children) and isinstance(children[idx], ast.ASTRef) and children[idx].name == 'EXTERN_PARAMS':
        params_node = children[idx]
        idx += 1

    if idx < len(children) and isinstance(children[idx], ast.ASTRef) and children[idx].name == 'ALIAS':
        alias_tokens = _flatten_values(children[idx])
        if len(alias_tokens) >= 2:
            alias_name = alias_tokens[1]

    if not alias_name:
        alias_name = c_name

    ret_type, is_ptr = _extract_type_info(type_node, has_ret_star) if type_node else ('void', False)

    params: list[dict[str, Any]] = []
    if params_node and isinstance(params_node, ast.ASTRef):
        for p in params_node.nodes:
            if isinstance(p, ast.ASTRef) and p.name == 'EXTERN_PARAM':
                p_star = False
                default_val = None

                p_tokens = _flatten_values(p)
                if '=' in p_tokens:
                    eq_idx = p_tokens.index('=')
                    if eq_idx + 1 < len(p_tokens):
                        default_val = p_tokens[eq_idx + 1]
                    p_tokens = p_tokens[:eq_idx]

                if '*' in p_tokens:
                    p_star = True
                    p_tokens = [t for t in p_tokens if t != '*']

                if len(p_tokens) >= 2:
                    p_type = p_tokens[0]
                    p_name = p_tokens[1]
                elif len(p_tokens) == 1:
                    p_type = p_tokens[0]
                    p_name = 'arg'
                else:
                    p_type = 'void'
                    p_name = 'arg'

                if p_star:
                    p_type = f'{p_type}*'

                params.append({
                    'name': p_name,
                    'type': p_type,
                    'default': default_val,
                    'has_default': default_val is not None,
                })

    return {
        'name': alias_name,
        'c_name': c_name,
        'return_type': ret_type,
        'is_pointer': is_ptr,
        'params': params,
    }


def parse_externs(source_or_file: str | Path) -> tuple[dict[str, dict], dict[str, Any]]:
    p = Path(str(source_or_file))
    if p.is_file():
        raw_code = p.read_text(encoding='utf-8')
    else:
        raw_code = str(source_or_file)

    clean_code, metadata = extract_directives(raw_code)

    if not clean_code.strip():
        return {}, metadata

    lexer = Lexer(clean_code)
    tokens = lexer.process()
    parser = Parser(tokens)
    nodes = parser.parse(extern_grammar, mode='Many')

    symbols: dict[str, dict] = {}
    if nodes:
        for node in nodes:
            info = extract_func(node)
            symbols[info['name']] = info
            if info['name'] != info['c_name']:
                symbols[info['c_name']] = info
    return symbols, metadata


__all__ = [
    'extract_directives',
    'extract_func',
    'parse_externs',
]
