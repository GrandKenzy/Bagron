from __future__ import annotations

from dataclasses import dataclass

from gram import ast as gast


@dataclass(frozen=True)
class VariableHandle:
    """Structural view of a variable declaration in any lexical scope."""

    declaration: gast.ASTRef
    name: str
    type_node: object
    value_node: object | None
    privacy: str
    pointer_level: int
    pointer_is_const: bool
    value_is_const: bool


def _token_value(node: object) -> object:
    token = getattr(node, 'token', None)
    return getattr(token, 'value', None)


def _declarator_info(node: gast.ASTRef) -> tuple[str, int, bool]:
    name = ''
    pointer_level = 0
    pointer_is_const = False

    for child in node.nodes:
        if isinstance(child, gast.ASTKeyword):
            pointer_is_const = child.token.value == 'const'
        elif isinstance(child, gast.ASTRef) and child.name == 'POINTER':
            pointer_level = len(child.nodes)
        else:
            value = _token_value(child)
            if value is not None:
                name = str(value)

    return name, pointer_level, pointer_is_const


def _type_is_const(node: object) -> bool:
    if isinstance(node, list):
        return any(_type_is_const(item) for item in node)
    if isinstance(node, gast.ASTRef):
        return _type_is_const(node.nodes)

    return _token_value(node) == 'const'


def handle_variable(node: gast.ASTRef) -> VariableHandle | None:
    """Extract one VAR node without resolving semantic values."""
    if node.name != 'VAR':
        return None

    privacy = 'public'
    declaration = next(
        (
            child for child in node.nodes
            if isinstance(child, gast.ASTRef)
            and child.name in ('VAR_DECLARATION', 'VAR_INITIALIZATION')
        ),
        None,
    )
    if declaration is None:
        return None

    for child in node.nodes:
        if isinstance(child, gast.ASTKeyword):
            privacy = str(child.token.value)
            break

    declarator_index = next(
        index for index, child in enumerate(declaration.nodes)
        if isinstance(child, gast.ASTRef) and child.name == 'DECLARATOR'
    )
    declarator = declaration.nodes[declarator_index]
    name, pointer_level, pointer_is_const = _declarator_info(declarator)
    type_node = declaration.nodes[declarator_index + 2]
    value_node = next(
        (
            child for child in declaration.nodes
            if isinstance(child, gast.ASTRef) and child.name == 'VALUE'
        ),
        None,
    )

    return VariableHandle(
        declaration=declaration,
        name=name,
        type_node=type_node,
        value_node=value_node,
        privacy=privacy,
        pointer_level=pointer_level,
        pointer_is_const=pointer_is_const,
        value_is_const=_type_is_const(type_node),
    )


GlobalVariableHandle = VariableHandle
handle_global_variable = handle_variable
