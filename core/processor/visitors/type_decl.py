from typing import Any
import gram
from core.processor.objects.type_decl import TypeDecl
from core.processor.visitors.call import extract_call_args

def _format_expr(tokens: list[Any]) -> str:
    tok_strs = [str(t.value if hasattr(t, 'value') else t) for t in tokens]
    if len(tok_strs) == 2 and tok_strs[0] == '__slot__':
        return f"{tok_strs[0]}[{tok_strs[1]}]"
    return ''.join(tok_strs)

def _extract_slot(stmt: gram.ASTNode) -> dict:
    spec_nodes = stmt.find('EGL_TYPE_SPEC')
    slot_type = 'any'
    if spec_nodes and spec_nodes[0].values:
        slot_type = str(spec_nodes[0].values[0])
    elif len(stmt.values) >= 2:
        slot_type = str(stmt.values[1])
    val_nodes = stmt.find('EGL_VALUE') or stmt.find('value')
    default_val = None
    if val_nodes and val_nodes[0].values:
        default_val = val_nodes[0].values[0]
    slot_name = None
    toks = [str(t.value if hasattr(t, 'value') else t) for t in getattr(stmt, 'all_tokens', [])]
    if len(toks) >= 3 and toks[2] != '=':
        slot_name = toks[2]
    return {'type': slot_type, 'name': slot_name, 'default': default_val}

def _extract_items(stmt: gram.ASTNode) -> list[str]:
    res = []
    for c in stmt.children:
        if c.name in ('EGL_VALUE', 'value', 'EGL_EXPRESSION', 'expression', 'EGL_INDEX_ACCESS'):
            all_toks = getattr(c, 'all_tokens', None)
            if all_toks:
                res.append(_format_expr(all_toks))
            elif c.values:
                res.append(str(c.values[0]))
    if not res:
        for val in stmt.values:
            val_str = str(val.value if hasattr(val, 'value') else val)
            if val_str not in ('__items__', ':'):
                res.append(val_str)
    return res

def visit(node: gram.ASTNode) -> TypeDecl:
    vals = [str(v.value if hasattr(v, 'value') else v) for v in node.values]
    privacy = 'public'
    if 'private' in vals:
        privacy = 'private'
    name = vals[-1]

    slots = []
    kind = None
    items = []
    dtype = None
    accessors = {}
    methods = {}

    body_nodes = node.find('EGL_TYPE_BODY') or node.find('body')
    if body_nodes:
        body = body_nodes[0]
        for stmt in body.children:
            if stmt.name in ('EGL_TYPE_SLOT', 'type slot'):
                slots.append(_extract_slot(stmt))
            elif stmt.name in ('EGL_TYPE_KIND', 'type kind'):
                if len(stmt.values) >= 2:
                    raw_kind = str(stmt.values[1].value if hasattr(stmt.values[1], 'value') else stmt.values[1])
                    kind = raw_kind.strip('\"\'')
            elif stmt.name in ('EGL_TYPE_ITEMS', 'type items'):
                items = _extract_items(stmt)
            elif stmt.name in ('EGL_TYPE_ACCESSOR', 'type accessor'):
                acc_name = None
                for val in stmt.values:
                    v_str = str(val.value if hasattr(val, 'value') else val)
                    if v_str in ('__getter__', '__setter__', '__getitem__', '__setitem__'):
                        acc_name = v_str
                        break
                if acc_name:
                    accessors[acc_name] = stmt
            elif stmt.name in ('EGL_TYPE_METHOD', 'type method'):
                m_name = str(stmt.values[2] if len(stmt.values) >= 3 else stmt.values[1])
                methods[m_name] = stmt

    field_spec = None
    field_args = []
    field_name = 'value'
    for f in (node.find('EGL_TYPE_FIELD') or []):
        spec_nodes = f.find('EGL_TYPE_SPEC')
        if spec_nodes and spec_nodes[0].values:
            spec_vals = [str(v.value if hasattr(v, 'value') else v) for v in spec_nodes[0].values]
            field_spec = spec_vals[0]
            if len(spec_vals) > 1:
                field_args = spec_vals[1:]
        for val in f.values:
            v_str = str(val.value if hasattr(val, 'value') else val)
            if v_str != field_spec and v_str not in field_args:
                field_name = v_str

    if field_spec:
        dtype = field_spec
        from core.processor.type_system import register_type
        register_type(name, field_spec, field_name, slots=slots, inner_args=field_args)
    elif 'Type' in vals:
        from core.processor.type_system import register_type
        register_type(name, dtype or '__int64_t__', field_name, slots=slots, inner_args=field_args)

    if 'Type' in vals:
        kind = 'Type'

    type_obj = TypeDecl(
        name=name,
        slots=slots,
        kind=kind,
        items=items,
        dtype=dtype,
        accessors=accessors,
        methods=methods,
        privacity=privacy
    )
    return type_obj
