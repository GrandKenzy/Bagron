"""Stable internal names shared by the frontend, LLVM backend and lib1.

Source names are deliberately kept out of this module's public contract.  A
Bagron symbol can therefore keep the spelling users write while LLVM receives
one deterministic, collision-resistant name.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import PurePath


MANGLE_VERSION = 'mangling-v1'


def _digest(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()[:length]


def _part(value: object) -> str:
    text = str(value)
    text = re.sub(r'[^A-Za-z0-9_]', '_', text)
    text = text.strip('_') or 'anon'
    return text[:64]


def module_key(module_path: object | None, project_root: object | None = None) -> str:
    # NOTA: Produce una clave canonica del modulo relativa a la raiz del proyecto o de Bagron.
    if module_path is None:
        return 'module'
    path = str(module_path).replace('\\', '/')
    if project_root is not None:
        root = str(project_root).replace('\\', '/').rstrip('/') + '/'
        if path.startswith(root):
            path = path[len(root):]
    from core.globvars import BAGRON_ROOT
    bagron_root_str = str(BAGRON_ROOT).replace('\\', '/').rstrip('/') + '/'
    if path.startswith(bagron_root_str):
        path = path[len(bagron_root_str):]
    return _part(PurePath(path).with_suffix('').as_posix())


def signature_key(signature: object | None) -> str:
    if signature is None:
        return 'nosig'
    parameters = []
    for parameter in getattr(signature, 'parameters', ()):
        spec = getattr(parameter, 'type_spec', None)
        parameters.append(
            ':'.join((
                str(getattr(spec, 'canonical_name', getattr(spec, 'name', ''))),
                'receiver' if getattr(parameter, 'is_receiver', False) else '',
                'len' if getattr(parameter, 'is_length', False) else '',
                'size' if getattr(parameter, 'is_size', False) else '',
                'signed' if getattr(parameter, 'is_signed', False) else '',
                'region' if getattr(parameter, 'is_region', False) else '',
            ))
        )
    result = ','.join(parameters)
    result += '->' + str(
        getattr(
            getattr(signature, 'return_type', None),
            'canonical_name',
            getattr(getattr(signature, 'return_type', None), 'name', 'void'),
        )
    )
    return _digest(result, 20)


def symbol_llvm_name(
    symbol: object,
    *,
    identity: str,
    project_root: object | None = None,
) -> str:
    """Return the one stable LLVM name for a frontend symbol."""
    name = str(getattr(symbol, 'name', ''))
    if name == 'main' or getattr(symbol, 'is_external', False):
        return name

    module = module_key(getattr(symbol, 'module_path', None), project_root)
    if getattr(symbol, 'is_method', False):
        owner = getattr(symbol, 'owner_type', None) or 'type'
        source = getattr(symbol, 'source_name', None) or name
        kind = 'method'
        readable = f'{owner}_{source}'
    elif hasattr(symbol, 'signature'):
        kind = 'fn'
        readable = name
    elif hasattr(symbol, 'type_spec'):
        kind = 'global'
        readable = name
    else:
        kind = 'type'
        readable = name

    signature = signature_key(getattr(symbol, 'signature', None))
    descriptor = f'{identity}\0{module}\0{kind}\0{name}\0{signature}'
    return (
        f'__bg_{_digest(identity)}_{_digest(module, 12)}_'
        f'{kind}_{_part(readable)}_{_digest(descriptor, 20)}'
    )


def package_identity(name: str, version: str, source_sha: str) -> str:
    return hashlib.sha256(
        f'{name}\0{version}\0{source_sha}'.encode('utf-8')
    ).hexdigest()


__all__ = [
    'MANGLE_VERSION',
    'module_key',
    'package_identity',
    'signature_key',
    'symbol_llvm_name',
]
