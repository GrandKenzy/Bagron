from typing import Any
import gram

def extract_call_args(call_node: gram.ASTNode) -> tuple[list[Any], dict[str, Any]]:
    pos_args: list[Any] = []
    kw_args: dict[str, Any] = {}
    if not call_node.children:
        return pos_args, kw_args
    args_container = call_node.children[0]
    for child in getattr(args_container, 'children', []):
        if child.name in ('EGL_ARG_ITEM', 'arg item'):
            toks = getattr(child, 'all_tokens', [])
            if len(toks) == 1 and getattr(toks[0], 'token', None) == gram.Token.STRING:
                pos_args.append(f'"{toks[0].value}"')
                continue
            if child.children and child.children[0].name in ('EGL_NAMED_ARG', 'named arg'):
                named_node = child.children[0]
                k = str(named_node.values[0].value if hasattr(named_node.values[0], 'value') else named_node.values[0])
                v = named_node.children[0].values[0] if named_node.children and named_node.children[0].values else None
                kw_args[k] = v
            elif child.find('EGL_INDEX_ACCESS'):
                idx_node = child.find('EGL_INDEX_ACCESS')[0]
                toks = [str(getattr(t, 'value', t)) for t in idx_node.all_tokens]
                if len(toks) >= 2:
                    pos_args.append(f'{toks[0]}[{toks[1]}]')
                elif idx_node.values:
                    pos_args.append(idx_node.values[0])
            elif hasattr(child, 'all_tokens') and len(child.all_tokens) > 1:
                tokens_str = [str(getattr(t, 'value', t)) for t in child.all_tokens]
                cleaned = ' '.join(tokens_str).replace(' . ', '.').replace('. ', '.').replace(' .', '.')
                pos_args.append(cleaned)
            elif child.children and child.children[0].values:
                pos_args.append(child.children[0].values[0])
            elif child.values:
                pos_args.append(child.values[0])
        elif child.name in ('EGL_NAMED_ARG', 'named arg'):
            k = str(child.values[0].value if hasattr(child.values[0], 'value') else child.values[0])
            v = child.children[0].values[0] if child.children and child.children[0].values else None
            kw_args[k] = v
        elif hasattr(child, 'values') and child.values:
            pos_args.append(child.values[0])
    if not pos_args and not kw_args and getattr(args_container, 'values', None):
        pos_args = list(args_container.values)
    return pos_args, kw_args
