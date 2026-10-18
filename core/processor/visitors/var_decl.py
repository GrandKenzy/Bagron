from gram import ast

from core.processor import typesys
from core.processor.objects import Variable
from core.processor.storage import Storage
from core.processor.typesys import SemanticError

_DECL_LEN = 5
_DECL_WITH_POINTER_LEN = 6


def lookup_variable(storage: Storage, name: str, token=None) -> Variable:
    """Busca una variable por nombre."""
    directory = storage.collition_name(name, False)
    if not directory:
        raise SemanticError(f"No existe ningún símbolo llamado '{name}'", token)

    entry = directory[name]
    if not isinstance(entry, Variable):
        raise SemanticError(f"'{name}' existe pero no es una variable", token)
    return entry


def _split_pointer(nodes: list[ast.ASTRef]):
    """Separa el modificador de puntero opcional (ptr/cptr) del resto."""
    if len(nodes) == _DECL_WITH_POINTER_LEN:
        pointer = nodes[0].token.value
        if pointer not in typesys.POINTER_KINDS:
            raise SemanticError(f"Modificador de puntero inválido '{pointer}'", nodes[0].token)
        return pointer, nodes[1:]
    if len(nodes) == _DECL_LEN:
        return None, nodes
    raise SemanticError(
        f'Declaración malformada: {len(nodes)} nodos '
        f'(se esperaban {_DECL_LEN} o {_DECL_WITH_POINTER_LEN})'
    )


def _is_null(node) -> bool:
    if isinstance(node, ast.LiteralSymbol): return node.token.token.name == 'NULL'
    else:
        return False


def _is_constant(name: str) -> bool:
    return name.isupper()


def _handle_full_decl(storage: Storage, nodes: list[ast.ASTRef], privacy: str) -> Variable:
    pointer, nodes = _split_pointer(nodes)
    name_node, _colon, type_node, _assign, value_node = nodes

    name: str = name_node.token.value

    if not isinstance(type_node, ast.ASTKeyword):
        raise SemanticError('Los arrays aún no están implementados', getattr(type_node, 'token', None))
    type_v: str = type_node.token.value
    info = typesys.get_type(type_v, type_node.token)

    if info.kind is typesys.Kind.VOID and pointer is None:
        raise SemanticError(f"'{name}' no puede ser de tipo void (usa ptr/cptr)", type_node.token)

    res = value_node.nodes[0]
    
    if _is_null(res):
        if not typesys.can_assign(type_v, pointer, typesys.NULL_TYPE, None):
            raise SemanticError(f"Null solo puede asignarse a ptr/cptr, no a '{name}: {type_v}'", res.token)
        value = None


    elif isinstance(res, ast.LiteralNumber):
        value = res.token.value
        if pointer:
            if value != 0:
                raise SemanticError(f"Un puntero solo puede inicializarse con 0 (nulo), no con {value}", res.token)
        elif not typesys.fits_literal(value, type_v):
            raise SemanticError(f"{value} no es un valor válido para '{type_v}'", res.token)

    elif isinstance(res, ast.Identifier):
        src = lookup_variable(storage, res.token.value, res.token)
        if not typesys.can_assign(type_v, pointer, src.type, src.pointer):
            raise SemanticError(
                f"No se puede asignar '{src.type}' a la variable '{name}' de tipo '{type_v}'",
                res.token,
            )
        # Un puntero copia la referencia; un escalar se convierte al tipo destino.
        value = src.value if pointer else typesys.convert(src.value, type_v)

    else:
        raise SemanticError(f'Valor no soportado: {res!r}', getattr(res, 'token', None))

    return Variable(name, value, type_v, privacy, _is_constant(name), pointer)


def visit_var(storage: Storage, node: ast.ASTRef) -> None:
    if len(node.nodes) == 2:  # noqa: PLR2004 - el primer nodo es la privacidad
        privacy = node.nodes[0].token.value
        node = node.nodes[1]
    else:
        privacy = storage.privacy
        node = node.nodes[0]

    if node.name != 'VAR_FULL_DECL':
        raise SemanticError(f"Tipo de declaración no soportado: '{node.name}'")

    storage.add_variable(_handle_full_decl(storage, node.nodes, privacy))


__all__ = ['visit_var']