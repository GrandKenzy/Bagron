from pathlib import Path
import re
from typing import Any
import gram
from core.externs.grammar import extern_grammar

def extract_directives(code: str) -> tuple[str, dict[str, Any]]:
    metadata = {
        'header': None,
        'links': [],
        'bins': [],
        'lib_dirs': [],
        'include_dirs': []
    }
    clean_lines = []
    for line in code.splitlines():
        trimmed = line.strip()
        if trimmed.startswith('@'):
            match = re.match(r'^@([A-Za-z0-9_]+)\s+(.+)$', trimmed)
            if match:
                directive = match.group(1).lower()
                val = match.group(2).strip().strip('"\'')
                if directive in ('header', 'c_header'):
                    metadata['header'] = val
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

def extract_func(node: gram.ASTNode) -> dict:
    vals_str = [str(v.value if hasattr(v, 'value') else v) for v in node.values]
    spec_nodes = node.find('EGL_TYPE_SPEC')
    is_ptr = False
    if spec_nodes and spec_nodes[0].values:
        spec_vals = [str(v.value if hasattr(v, 'value') else v) for v in spec_nodes[0].values]
        if spec_vals[0] == '__void_p_t__' and len(spec_vals) > 1:
            ret_type = spec_vals[1]
            is_ptr = True
        else:
            ret_type = spec_vals[0]
            if '*' in spec_vals or (len(vals_str) > 1 and vals_str[0] == '*'):
                is_ptr = True
    elif vals_str:
        ret_type = vals_str.pop(0)
    else:
        ret_type = 'void'

    orig_name = ''
    for v in vals_str:
        if v not in ('*', 'as'):
            orig_name = v
            break
    alias_name = orig_name
    if 'as' in vals_str:
        as_pos = vals_str.index('as')
        if as_pos + 1 < len(vals_str):
            alias_name = vals_str[as_pos + 1]
    
    params = []
    params_node = node.find_first('EGL_PARAMS')
    if params_node:
        for p in params_node.find('EGL_PARAM'):
            p_spec = p.find('EGL_TYPE_SPEC')
            if p_spec and p_spec[0].values:
                p_svals = [str(v.value if hasattr(v, 'value') else v) for v in p_spec[0].values]
                if p_svals[0] == '__void_p_t__' and len(p_svals) > 1:
                    p_type = f'{p_svals[1]}*'
                else:
                    p_type = p_svals[0]
            elif p.values:
                p_type = str(p.values[0].value if hasattr(p.values[0], 'value') else p.values[0])
            else:
                p_type = 'all'
            p_name = str(p.values[-1].value if hasattr(p.values[-1], 'value') else p.values[-1]) if p.values else 'arg'
            default_val = None
            v_node = p.find_first('EGL_VALUE')
            if v_node and v_node.values:
                default_val = v_node.values[0].value if hasattr(v_node.values[0], 'value') else v_node.values[0]
            params.append({
                'name': p_name,
                'type': p_type,
                'default': default_val,
                'has_default': default_val is not None
            })
    return {
        'name': alias_name,
        'c_name': orig_name,
        'return_type': ret_type,
        'is_pointer': is_ptr,
        'params': params
    }

def parse_externs(source_or_file: str | Path) -> tuple[dict[str, dict], dict[str, Any]]:
    p = Path(str(source_or_file))
    if p.is_file():
        raw_code = p.read_text(encoding='utf-8')
    else:
        raw_code = str(source_or_file)

    clean_code, metadata = extract_directives(raw_code)

    ast = gram.process(extern_grammar, source_or_file=clean_code)
    symbols = {}
    if ast and hasattr(ast, 'body'):
        for node in ast.body:
            info = extract_func(node)
            symbols[info['name']] = info
            if info['name'] != info['c_name']:
                symbols[info['c_name']] = info
    return symbols, metadata
