from pathlib import Path

from gram import ast

from core.processor.storage import Storage

__DIR_EXTERNS: list[str] = [
    'externs',
]


WARNS: list[str] = []


def _find_extern(storage: Storage, name: str) -> Path | None:
    clean_name = name.strip('"\'')
    clean_name = clean_name.removesuffix('.h')

    # Convención oficial esperada: *.externs.egl
    expected_filename = f'{clean_name}.externs.egl'

    for folder in __DIR_EXTERNS:
        folder_path = Path(folder)
        base = folder_path if folder_path.is_absolute() else storage.root.parent / folder_path
        if not base.exists():
            continue

        target = base / expected_filename
        if target.exists():
            return target

        # Warn si encuentra un archivo que no sigue la convención *.externs.egl
        fallback = base / f'{clean_name}.extern.egl'
        if fallback.exists():
            warn_msg = f"El archivo '{fallback.name}' no sigue la convención '{expected_filename}'."
            WARNS.append(warn_msg)
            storage.add_warning(warn_msg)
            return fallback

    return None


def _charge(storage: Storage, name: str) -> bool:
    clean_name = name.strip('"\'')
    target = _find_extern(storage, clean_name)
    if not target:
        return False

    return True



def visit_include(storage: Storage, node: ast.ASTRef):
    second_node = node.nodes[1]

    # Caso destructurado: include { a, b as B } from "header.h"
    if isinstance(second_node, ast.ASTRef) and second_node.name == 'IMPORT_GROUP':
        header_name = node.nodes[3].token.value  # type: ignore
        clean_header = header_name.strip('"\'')
        if _charge(storage, clean_header):
            if clean_header not in storage.includes:
                storage.add_include(clean_header, None)

            array_node: ast.ArrayNode = second_node.nodes[0]  # type: ignore
            for spec in array_node.items:  # type: ignore
                symbol = spec.nodes[0].token.value  # type: ignore
                alias = spec.nodes[1].nodes[1].token.value if len(spec.nodes) == 2 else None  # type: ignore
                key = alias or symbol
                if key in storage.declarations:
                    raise RuntimeError(f"Colisión de include: el símbolo '{key}' ya existe.")
                storage.add_declaration(f"{clean_header}|{symbol}", key)
        return

    # Caso tradicional: include "header.h" [as alias]
    name = second_node.token.value  # type: ignore
    clean_name = name.strip('"\'')
    alias = None

    if len(node.nodes) == 3:
        alias_node = node.nodes[2]
        alias = alias_node.nodes[1].token.value  # type: ignore

    if _charge(storage, clean_name):
        target_key = alias if alias else clean_name
        if target_key in storage.includes:
            existing = storage.includes[target_key]
            expected = None if not alias else clean_name
            if existing != expected:
                raise RuntimeError(f"Colisión de include: '{target_key}'")
            return

        storage.add_include(clean_name, alias)


