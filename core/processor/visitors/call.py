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
            if child.children and child.children[0].name in ('EGL_NAMED_ARG', 'named arg'):
                named_node = child.children[0]
                k = str(named_node.values[0].value if hasattr(named_node.values[0], 'value') else named_node.values[0])
                v = named_node.children[0].values[0] if named_node.children and named_node.children[0].values else None
                kw_args[k] = v
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
