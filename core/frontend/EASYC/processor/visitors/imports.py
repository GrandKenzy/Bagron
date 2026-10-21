from pathlib import Path

from gram import ast

from core.processor.storage import Storage


__DIR_MODULES: list[str] = [
    'modules',
]


def _find_module(storage: Storage, name: str) -> Path | None:
    """Busca un módulo a nivel 1 dentro de la carpeta 'modules'. No permite subcarpetas."""
    from core.compiler import Environment

    base_dir = Environment.basedir if Environment.basedir is not None else storage.root.parent
    candidate = (base_dir / 'modules' / f'{name}.egl').resolve()
    if candidate.exists() and candidate.is_file():
        return candidate

    fallback = (storage.root.parent / 'modules' / f'{name}.egl').resolve()
    if fallback.exists() and fallback.is_file():
        return fallback

    return None


def _charge(storage: Storage, name: str) -> bool:
    main_ref = storage.main_storage or storage

    target = _find_module(storage, name)
    if not target:
        return False

    # 1. Si ya fue procesado y cacheado canónicamente, reutilizar sin re-parsear
    if target in main_ref.loaded_modules:
        cached_storage = main_ref.loaded_modules[target]
        storage.modules[name] = cached_storage
        return True

    # 2. Detección de ciclo de dependencia
    if target in main_ref.in_progress:
        raise RuntimeError(
            f"Dependencia circular detectada al importar el módulo '{name}' ({target.name})."
        )

    # 3. Procesar módulo registrando en progreso
    main_ref.in_progress.add(target)
    try:
        from core.compiler import compile_source
        module_storage = compile_source(target, main_storage=main_ref)
    finally:
        main_ref.in_progress.remove(target)

    # 4. Guardar en cache canónica y en los diccionarios de módulos
    main_ref.loaded_modules[target] = module_storage
    main_ref.add_module(name, module_storage)
    if storage is not main_ref:
        storage.modules[name] = module_storage

    return True



def visit_import(storage: Storage, node: ast.ASTRef):
    second_node = node.nodes[1]

    # Caso destructurado: import { a, b as B } from modulo
    if isinstance(second_node, ast.ASTRef) and second_node.name == 'IMPORT_GROUP':
        module_name = node.nodes[3].token.value  # type: ignore
        if _charge(storage, module_name):
            if module_name not in storage.imports:
                storage.add_import(module_name, None)

            array_node: ast.ArrayNode = second_node.nodes[0]  # type: ignore
            for spec in array_node.items:  # type: ignore
                symbol = spec.nodes[0].token.value  # type: ignore
                alias = spec.nodes[1].nodes[1].token.value if len(spec.nodes) == 2 else None  # type: ignore
                key = alias or symbol
                if key in storage.declarations:
                    raise RuntimeError(f"Colisión de importación: el símbolo '{key}' ya existe.")
                storage.add_declaration(f"{module_name}|{symbol}", key)
        return

    # Caso tradicional: import modulo [as alias]
    name = second_node.token.value  # type: ignore
    alias = None

    if len(node.nodes) == 3:
        alias_node = node.nodes[2]
        alias = alias_node.nodes[1].token.value  # type: ignore

    if _charge(storage, name):
        target_key = alias if alias else name
        if target_key in storage.imports:
            existing = storage.imports[target_key]
            expected = None if not alias else name
            if existing != expected:
                raise RuntimeError(f"Colisión de importación: '{target_key}'")
            return

        storage.add_import(name, alias)
        if alias and name in storage.modules:
            storage.modules[alias] = storage.modules[name]



__all__ = [
    'visit_import',
]
